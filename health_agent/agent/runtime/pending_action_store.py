"""PendingAction Store Port 与内存 Adapter。"""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Protocol

from agent.runtime.pending_action import PendingAction, copy_pending_action, utc_now


class PendingActionStoreError(RuntimeError):
    """PendingActionStore 基础异常。"""


class PendingActionAlreadyExistsError(PendingActionStoreError):
    """PendingAction 已存在。"""


class PendingActionNotFoundError(PendingActionStoreError):
    """PendingAction 不存在。"""


class PendingActionVersionConflictError(PendingActionStoreError):
    """PendingAction version 与 expected_version 不一致。"""


class PendingActionStore(Protocol):
    """PendingAction 持久化端口。"""

    def create(self, action: PendingAction) -> PendingAction:
        """创建 PendingAction。"""
        ...

    def get(self, action_id: str) -> PendingAction | None:
        """按 action_id 读取 PendingAction。"""
        ...

    def save(self, action: PendingAction, expected_version: int) -> PendingAction:
        """按 expected_version 乐观保存 PendingAction。"""
        ...


class InMemoryPendingActionStore:
    """线程安全的内存 PendingActionStore。"""

    def __init__(self) -> None:
        self._actions: dict[str, PendingAction] = {}
        self._lock = RLock()

    def create(self, action: PendingAction) -> PendingAction:
        """创建并返回独立快照。"""
        snapshot = copy_pending_action(action)
        with self._lock:
            if snapshot.action_id in self._actions:
                raise PendingActionAlreadyExistsError(
                    f"PendingAction already exists: {snapshot.action_id}"
                )
            self._actions[snapshot.action_id] = copy_pending_action(snapshot)
            return copy_pending_action(snapshot)

    def get(self, action_id: str) -> PendingAction | None:
        """读取 PendingAction；不存在时返回 None。"""
        normalized = str(action_id or "").strip()
        with self._lock:
            action = self._actions.get(normalized)
            return copy_pending_action(action) if action is not None else None

    def save(self, action: PendingAction, expected_version: int) -> PendingAction:
        """使用 compare-and-swap 语义保存 PendingAction。"""
        if expected_version < 0:
            raise PendingActionVersionConflictError("expected_version must be non-negative")
        snapshot = copy_pending_action(action)
        with self._lock:
            current = self._actions.get(snapshot.action_id)
            if current is None:
                raise PendingActionNotFoundError(
                    f"PendingAction not found: {snapshot.action_id}"
                )
            if current.version != expected_version:
                raise PendingActionVersionConflictError(
                    f"PendingAction version conflict: expected {expected_version}, "
                    f"got {current.version}"
                )
            saved = replace(
                snapshot,
                version=current.version + 1,
                updated_at=utc_now(),
            )
            self._actions[saved.action_id] = copy_pending_action(saved)
            return copy_pending_action(saved)

    def list_all(self) -> list[PendingAction]:
        """维护接口：返回全部 PendingAction 快照，不暴露内部可变对象。"""

        with self._lock:
            return [copy_pending_action(action) for action in self._actions.values()]

    def delete(self, action_id: str, expected_version: int) -> None:
        """维护接口：按 expected_version 删除 PendingAction。"""

        if expected_version < 0:
            raise PendingActionVersionConflictError("expected_version must be non-negative")
        normalized = str(action_id or "").strip()
        with self._lock:
            current = self._actions.get(normalized)
            if current is None:
                raise PendingActionNotFoundError(
                    f"PendingAction not found: {normalized}"
                )
            if current.version != expected_version:
                raise PendingActionVersionConflictError(
                    f"PendingAction version conflict: expected {expected_version}, "
                    f"got {current.version}"
                )
            del self._actions[normalized]
