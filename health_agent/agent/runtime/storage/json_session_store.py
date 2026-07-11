"""AgentSession 的 JSON 文件 Store Adapter。

该 Store 是显式选择的本地持久化实现：每个 session_id 映射为一个 SHA-256 文件键，
create/save 在实体级 `.lock` 文件内完成，CAS 比较以磁盘当前 version 为准。它不实现
RUNNING lease、stale owner recovery 或 orphan PendingAction 清理。
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from agent.runtime.session import (
    AgentSession,
    SessionAlreadyExistsError,
    SessionNotFoundError,
    SessionStoreError,
    SessionVersionConflictError,
    copy_session,
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
    safe_entity_key,
    session_from_payload,
    session_to_payload,
)


class JsonSessionStoreDataCorrupted(SessionStoreError):
    """Session JSON 文件存在但内容损坏或与请求 ID 不匹配。"""


class JsonSessionStoreUnsupportedSchema(JsonSessionStoreDataCorrupted):
    """Session JSON 文件 schema_version 不受当前代码支持。"""


class JsonSessionStoreIOError(SessionStoreError):
    """Session JSON Store 发生文件系统读写或锁错误。"""


class JsonFileSessionStore:
    """基于 JSON 文件的 AgentSession Store。

    目录布局：
    `<data_dir>/sessions/<sha256(session_id)>.json`
    `<data_dir>/sessions/<sha256(session_id)>.lock`

    JSON 文件是明文，可能包含用户消息、assistant 消息和 Tool Result，只适合受控
    本地环境；本 Slice 不提供静态加密。
    """

    def __init__(
        self,
        data_dir: Path | str,
        *,
        now_provider: Callable[[], datetime] | None = None,
        atomic_writer: Callable[[Path, str], None] = atomic_write_text,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.sessions_dir = self.data_dir / "sessions"
        self.now_provider = now_provider
        self.atomic_writer = atomic_writer
        ensure_private_directory(self.data_dir)
        ensure_private_directory(self.sessions_dir)

    def create(
        self,
        session: AgentSession | None = None,
        *,
        session_id: str | None = None,
        locale: str = "zh-CN",
    ) -> AgentSession:
        """创建 Session；重复 create 必须失败，不能覆盖已有 JSON 文件。"""

        if session is None:
            now = self._utc_now()
            session = AgentSession(
                session_id=session_id or f"session-{uuid4().hex}",
                locale=locale,
                created_at=now,
                updated_at=now,
            )
        snapshot = copy_session(session)
        snapshot = replace(snapshot, version=0)
        paths = self._paths(snapshot.session_id)
        with self._locked(paths.lock_path):
            if paths.json_path.exists():
                raise SessionAlreadyExistsError("Session already exists")
            self._write_unlocked(paths.json_path, session_to_payload(snapshot))
            return copy_session(snapshot)

    def get(self, session_id: str) -> AgentSession | None:
        """读取 Session；文件不存在返回 None，损坏文件抛出 corruption 错误。"""

        normalized = str(session_id or "").strip()
        if not normalized:
            return None
        paths = self._paths(normalized)
        with self._locked(paths.lock_path):
            return self._read_unlocked(paths.json_path, expected_session_id=normalized)

    def save(self, session: AgentSession, expected_version: int) -> AgentSession:
        """使用磁盘当前 version 做 CAS 保存，并返回独立快照。"""

        if expected_version < 0:
            raise SessionVersionConflictError("expected_version must be non-negative")
        snapshot = copy_session(session)
        paths = self._paths(snapshot.session_id)
        with self._locked(paths.lock_path):
            current = self._read_unlocked(
                paths.json_path,
                expected_session_id=snapshot.session_id,
            )
            if current is None:
                raise SessionNotFoundError("Session not found")
            if current.version != expected_version:
                raise SessionVersionConflictError("Session version conflict")
            saved = replace(
                snapshot,
                session_id=current.session_id,
                version=current.version + 1,
                created_at=current.created_at,
                updated_at=self._utc_now(),
            )
            self._write_unlocked(paths.json_path, session_to_payload(saved))
            return copy_session(saved)

    def get_or_create(
        self,
        session_id: str | None = None,
        locale: str = "zh-CN",
    ) -> AgentSession:
        """兼容 GenericAgentLoop 现有调用：存在则读取，不存在则创建。"""

        if session_id:
            existing = self.get(session_id)
            if existing is not None:
                return existing
        return self.create(session_id=session_id, locale=locale)

    def _paths(self, session_id: str) -> "_EntityPaths":
        key = safe_entity_key(session_id)
        return _EntityPaths(
            json_path=self.sessions_dir / f"{key}.json",
            lock_path=self.sessions_dir / f"{key}.lock",
        )

    @contextmanager
    def _locked(self, lock_path: Path):
        try:
            with entity_lock(lock_path):
                yield
        except JsonStoreIOError as exc:
            raise JsonSessionStoreIOError("Session store lock failed") from exc

    def _read_unlocked(
        self,
        json_path: Path,
        *,
        expected_session_id: str,
    ) -> AgentSession | None:
        try:
            text = json_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise JsonSessionStoreIOError("Session store read failed") from exc
        except UnicodeDecodeError as exc:
            raise JsonSessionStoreDataCorrupted("Session JSON is not UTF-8") from exc
        try:
            return session_from_payload(
                loads_payload(text),
                expected_session_id=expected_session_id,
            )
        except JsonStoreUnsupportedSchema as exc:
            raise JsonSessionStoreUnsupportedSchema("Session schema is not supported") from exc
        except JsonStoreDataCorrupted as exc:
            raise JsonSessionStoreDataCorrupted("Session JSON is corrupted") from exc

    def _write_unlocked(self, json_path: Path, payload: Mapping[str, object]) -> None:
        try:
            self.atomic_writer(json_path, dumps_payload(payload))
        except JsonStoreIOError as exc:
            raise JsonSessionStoreIOError("Session store write failed") from exc

    def _utc_now(self) -> datetime:
        value = self.now_provider() if self.now_provider else datetime.now(UTC)
        if value.tzinfo is None or value.utcoffset() is None:
            raise JsonSessionStoreIOError("Session store clock must be timezone-aware")
        return value.astimezone(UTC)


class _EntityPaths:
    """同一实体的 JSON 文件与 lock 文件路径。"""

    def __init__(self, *, json_path: Path, lock_path: Path) -> None:
        self.json_path = json_path
        self.lock_path = lock_path
