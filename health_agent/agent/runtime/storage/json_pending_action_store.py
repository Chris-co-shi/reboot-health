"""PendingAction 的 JSON 文件 Store Adapter。

每个 action_id 使用独立 JSON 文件和 lock 文件。save 时重新读取磁盘当前 Action 并
比较 expected_version，确保多进程并发下不会 last-write-wins。
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Callable, Mapping

from agent.runtime.pending_action import PendingAction, copy_pending_action
from agent.runtime.pending_action_store import (
    PendingActionAlreadyExistsError,
    PendingActionNotFoundError,
    PendingActionStoreError,
    PendingActionVersionConflictError,
)
from agent.runtime.storage.atomic_file import atomic_write_text, ensure_private_directory
from agent.runtime.storage.errors import (
    JsonStoreDataCorrupted,
    JsonStoreIOError,
    JsonStoreUnsupportedSchema,
)
from agent.runtime.storage.file_lock import entity_lock
from agent.runtime.storage.json_codec import (
    dumps_payload,
    loads_payload,
    pending_action_from_payload,
    pending_action_to_payload,
    safe_entity_key,
)


class JsonPendingActionStoreDataCorrupted(PendingActionStoreError):
    """PendingAction JSON 文件存在但内容损坏或 hash 不匹配。"""


class JsonPendingActionStoreUnsupportedSchema(JsonPendingActionStoreDataCorrupted):
    """PendingAction JSON 文件 schema_version 不受当前代码支持。"""


class JsonPendingActionStoreIOError(PendingActionStoreError):
    """PendingAction JSON Store 发生文件系统读写或锁错误。"""


class JsonFilePendingActionStore:
    """基于 JSON 文件的 PendingAction Store。

    目录布局：
    `<data_dir>/pending-actions/<sha256(action_id)>.json`
    `<data_dir>/pending-actions/<sha256(action_id)>.lock`
    """

    def __init__(
        self,
        data_dir: Path | str,
        *,
        now_provider: Callable[[], datetime] | None = None,
        atomic_writer: Callable[[Path, str], None] = atomic_write_text,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.actions_dir = self.data_dir / "pending-actions"
        self.now_provider = now_provider
        self.atomic_writer = atomic_writer
        ensure_private_directory(self.data_dir)
        ensure_private_directory(self.actions_dir)

    def create(self, action: PendingAction) -> PendingAction:
        """创建 PendingAction；重复 action_id 不会覆盖已有快照。"""

        snapshot = replace(copy_pending_action(action), version=0)
        paths = self._paths(snapshot.action_id)
        with self._locked(paths.lock_path):
            if paths.json_path.exists():
                raise PendingActionAlreadyExistsError("PendingAction already exists")
            self._write_unlocked(paths.json_path, pending_action_to_payload(snapshot))
            return copy_pending_action(snapshot)

    def get(self, action_id: str) -> PendingAction | None:
        """读取 PendingAction；不存在返回 None，损坏文件抛出 corruption 错误。"""

        normalized = str(action_id or "").strip()
        if not normalized:
            return None
        paths = self._paths(normalized)
        with self._locked(paths.lock_path):
            return self._read_unlocked(paths.json_path, expected_action_id=normalized)

    def save(self, action: PendingAction, expected_version: int) -> PendingAction:
        """使用磁盘当前 version 做 CAS 保存，并保持 created_at 不可被调用方篡改。"""

        if expected_version < 0:
            raise PendingActionVersionConflictError("expected_version must be non-negative")
        snapshot = copy_pending_action(action)
        paths = self._paths(snapshot.action_id)
        with self._locked(paths.lock_path):
            current = self._read_unlocked(
                paths.json_path,
                expected_action_id=snapshot.action_id,
            )
            if current is None:
                raise PendingActionNotFoundError("PendingAction not found")
            if current.version != expected_version:
                raise PendingActionVersionConflictError("PendingAction version conflict")
            saved = replace(
                snapshot,
                action_id=current.action_id,
                version=current.version + 1,
                created_at=current.created_at,
                updated_at=self._utc_now(),
            )
            self._write_unlocked(paths.json_path, pending_action_to_payload(saved))
            return copy_pending_action(saved)

    def list_all(self) -> list[PendingAction]:
        """维护接口：列出全部 PendingAction 快照。"""

        actions: list[PendingAction] = []
        try:
            json_paths = sorted(self.actions_dir.glob("*.json"))
        except OSError as exc:
            raise JsonPendingActionStoreIOError("PendingAction store list failed") from exc
        for json_path in json_paths:
            lock_path = self.actions_dir / f"{json_path.stem}.lock"
            with self._locked(lock_path):
                action = self._read_unlocked_without_expected_id(json_path)
                if action is not None:
                    if safe_entity_key(action.action_id) != json_path.stem:
                        raise JsonPendingActionStoreDataCorrupted(
                            "PendingAction id does not match file key"
                        )
                    actions.append(action)
        return actions

    def delete(self, action_id: str, expected_version: int) -> None:
        """维护接口：按 expected_version 删除 PendingAction JSON 文件。"""

        if expected_version < 0:
            raise PendingActionVersionConflictError("expected_version must be non-negative")
        normalized = str(action_id or "").strip()
        if not normalized:
            raise PendingActionNotFoundError("PendingAction not found")
        paths = self._paths(normalized)
        with self._locked(paths.lock_path):
            current = self._read_unlocked(
                paths.json_path,
                expected_action_id=normalized,
            )
            if current is None:
                raise PendingActionNotFoundError("PendingAction not found")
            if current.version != expected_version:
                raise PendingActionVersionConflictError("PendingAction version conflict")
            try:
                paths.json_path.unlink()
                _fsync_directory_best_effort(self.actions_dir)
            except FileNotFoundError as exc:
                raise PendingActionNotFoundError("PendingAction not found") from exc
            except OSError as exc:
                raise JsonPendingActionStoreIOError("PendingAction store delete failed") from exc

    def _paths(self, action_id: str) -> "_EntityPaths":
        key = safe_entity_key(action_id)
        return _EntityPaths(
            json_path=self.actions_dir / f"{key}.json",
            lock_path=self.actions_dir / f"{key}.lock",
        )

    @contextmanager
    def _locked(self, lock_path: Path):
        try:
            with entity_lock(lock_path):
                yield
        except JsonStoreIOError as exc:
            raise JsonPendingActionStoreIOError("PendingAction store lock failed") from exc

    def _read_unlocked(
        self,
        json_path: Path,
        *,
        expected_action_id: str,
    ) -> PendingAction | None:
        try:
            text = json_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise JsonPendingActionStoreIOError("PendingAction store read failed") from exc
        except UnicodeDecodeError as exc:
            raise JsonPendingActionStoreDataCorrupted("PendingAction JSON is not UTF-8") from exc
        try:
            return pending_action_from_payload(
                loads_payload(text),
                expected_action_id=expected_action_id,
            )
        except JsonStoreUnsupportedSchema as exc:
            raise JsonPendingActionStoreUnsupportedSchema(
                "PendingAction schema is not supported"
            ) from exc
        except JsonStoreDataCorrupted as exc:
            raise JsonPendingActionStoreDataCorrupted("PendingAction JSON is corrupted") from exc

    def _read_unlocked_without_expected_id(
        self,
        json_path: Path,
    ) -> PendingAction | None:
        try:
            text = json_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise JsonPendingActionStoreIOError("PendingAction store read failed") from exc
        except UnicodeDecodeError as exc:
            raise JsonPendingActionStoreDataCorrupted("PendingAction JSON is not UTF-8") from exc
        try:
            return pending_action_from_payload(loads_payload(text))
        except JsonStoreUnsupportedSchema as exc:
            raise JsonPendingActionStoreUnsupportedSchema(
                "PendingAction schema is not supported"
            ) from exc
        except JsonStoreDataCorrupted as exc:
            raise JsonPendingActionStoreDataCorrupted("PendingAction JSON is corrupted") from exc

    def _write_unlocked(self, json_path: Path, payload: Mapping[str, object]) -> None:
        try:
            self.atomic_writer(json_path, dumps_payload(payload))
        except JsonStoreIOError as exc:
            raise JsonPendingActionStoreIOError("PendingAction store write failed") from exc

    def _utc_now(self) -> datetime:
        value = self.now_provider() if self.now_provider else datetime.now(UTC)
        if value.tzinfo is None or value.utcoffset() is None:
            raise JsonPendingActionStoreIOError("PendingAction store clock must be timezone-aware")
        return value.astimezone(UTC)


class _EntityPaths:
    """同一实体的 JSON 文件与 lock 文件路径。"""

    def __init__(self, *, json_path: Path, lock_path: Path) -> None:
        self.json_path = json_path
        self.lock_path = lock_path


def _fsync_directory_best_effort(path: Path) -> None:
    """尽力把删除动作同步到目录项；不支持目录 fsync 的平台静默降级。"""

    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        return
    finally:
        os.close(fd)
