"""Session Runtime。

Session 只记录 Python Runtime 内部运行状态，不保存确认事实，也不替代后续
受控确认、持久化和审计边界。当前实现只提供内存存储，便于 AgentLoop 在一次
测试或本地运行中具备 Session 能力。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock
from typing import Protocol
from uuid import uuid4

from agent.models import ModelMessage, ModelToolCall
from agent.models.base import mutable_mapping
from agent.runtime.continuation import AgentContinuation
from agent.runtime.state import RunStatus


class AgentSessionStatus(StrEnum):
    """跨多个用户输入的 Session 生命周期。"""

    ACTIVE = "active"
    RUNNING = "running"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"


def utc_now() -> datetime:
    """返回 UTC aware 当前时间。"""

    return datetime.now(UTC)


@dataclass
class AgentSession:
    """一次 Agent 交互会话的运行时状态。"""

    session_id: str
    status: AgentSessionStatus = AgentSessionStatus.ACTIVE
    messages: list[ModelMessage] = field(default_factory=list)
    pending_action_id: str | None = None
    continuation: AgentContinuation | None = None
    active_run_id: str | None = None
    run_fence_generation: int = 0
    active_run_last_heartbeat_at: datetime | None = None
    active_run_lease_expires_at: datetime | None = None
    version: int = 0
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    current_skill: str | None = None
    turns: int = 0
    pending_confirmations: list[str] = field(default_factory=list)
    context_summary: str = ""
    locale: str = "zh-CN"

    def __post_init__(self) -> None:
        session_id = str(self.session_id or "").strip()
        if not session_id:
            raise ValueError("session_id must not be empty")
        self.session_id = session_id
        self.status = _coerce_session_status(self.status)
        self.messages = _copy_messages(self.messages)
        if self.pending_action_id is not None:
            pending_action_id = str(self.pending_action_id or "").strip()
            self.pending_action_id = pending_action_id or None
        if self.active_run_id is not None:
            active_run_id = str(self.active_run_id or "").strip()
            self.active_run_id = active_run_id or None
        if not isinstance(self.run_fence_generation, int) or self.run_fence_generation < 0:
            raise ValueError("run_fence_generation must be a non-negative integer")
        self.active_run_last_heartbeat_at = _optional_aware_utc(
            self.active_run_last_heartbeat_at,
            "active_run_last_heartbeat_at",
        )
        self.active_run_lease_expires_at = _optional_aware_utc(
            self.active_run_lease_expires_at,
            "active_run_lease_expires_at",
        )
        if self.status == AgentSessionStatus.RUNNING:
            if not self.active_run_id:
                raise ValueError("RUNNING session must have active_run_id")
            if self.run_fence_generation <= 0:
                raise ValueError("RUNNING session must have positive run_fence_generation")
            if self.active_run_last_heartbeat_at is None:
                raise ValueError("RUNNING session must have active_run_last_heartbeat_at")
            if self.active_run_lease_expires_at is None:
                raise ValueError("RUNNING session must have active_run_lease_expires_at")
            if self.active_run_lease_expires_at <= self.active_run_last_heartbeat_at:
                raise ValueError("RUNNING session lease must expire after heartbeat")
        else:
            if self.active_run_id is not None:
                raise ValueError("non-RUNNING session must not have active_run_id")
            if self.active_run_last_heartbeat_at is not None:
                raise ValueError("non-RUNNING session must not have active_run_last_heartbeat_at")
            if self.active_run_lease_expires_at is not None:
                raise ValueError("non-RUNNING session must not have active_run_lease_expires_at")
        if not isinstance(self.version, int) or self.version < 0:
            raise ValueError("version must be a non-negative integer")
        if not isinstance(self.turns, int) or self.turns < 0:
            raise ValueError("turns must be a non-negative integer")
        self.created_at = _require_aware_utc(self.created_at, "created_at")
        self.updated_at = _require_aware_utc(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        self.pending_confirmations = list(self.pending_confirmations or [])
        self.context_summary = str(self.context_summary or "")
        self.locale = str(self.locale or "zh-CN")


class SessionStoreError(RuntimeError):
    """SessionStore 基础异常。"""


class SessionAlreadyExistsError(SessionStoreError):
    """Session 已存在。"""


class SessionNotFoundError(SessionStoreError):
    """Session 不存在。"""


class SessionVersionConflictError(SessionStoreError):
    """Session version 与 expected_version 不一致。"""


class SessionRunFenceLostError(SessionStoreError):
    """当前 Run 已失去 active_run_id 或 fence generation ownership。"""


class SessionRunLeaseExpiredError(SessionStoreError):
    """当前 Run 的 Session lease 已过期，旧 owner 不得继续写入。"""


class SessionStore(Protocol):
    """Session 持久化端口。"""

    def create(self, session: AgentSession) -> AgentSession:
        """创建 Session。"""
        ...

    def get(self, session_id: str) -> AgentSession | None:
        """读取 Session。"""
        ...

    def save(self, session: AgentSession, expected_version: int) -> AgentSession:
        """按 expected_version 乐观保存 Session。"""
        ...


class InMemorySessionStore:
    """仅用于本地运行和测试的内存 SessionStore。"""

    def __init__(self) -> None:
        self._sessions: dict[str, AgentSession] = {}
        self._lock = RLock()

    def create(
        self,
        session: AgentSession | None = None,
        *,
        session_id: str | None = None,
        locale: str = "zh-CN",
    ) -> AgentSession:
        """创建并保存一个新 session。"""
        snapshot = copy_session(
            session
            if session is not None
            else AgentSession(
                session_id=session_id or f"session-{uuid4().hex}",
                locale=locale,
            )
        )
        with self._lock:
            if snapshot.session_id in self._sessions:
                raise SessionAlreadyExistsError(
                    f"Session already exists: {snapshot.session_id}"
                )
            self._sessions[snapshot.session_id] = copy_session(snapshot)
            return copy_session(snapshot)

    def get(self, session_id: str) -> AgentSession | None:
        """按 session_id 查找 session。"""
        normalized = str(session_id or "").strip()
        with self._lock:
            session = self._sessions.get(normalized)
            return copy_session(session) if session is not None else None

    def save(self, session: AgentSession, expected_version: int) -> AgentSession:
        """使用 compare-and-swap 语义保存 session。"""
        if expected_version < 0:
            raise SessionVersionConflictError("expected_version must be non-negative")
        snapshot = copy_session(session)
        with self._lock:
            current = self._sessions.get(snapshot.session_id)
            if current is None:
                raise SessionNotFoundError(f"Session not found: {snapshot.session_id}")
            if current.version != expected_version:
                raise SessionVersionConflictError(
                    f"Session version conflict: expected {expected_version}, "
                    f"got {current.version}"
                )
            saved = replace(
                snapshot,
                version=current.version + 1,
                updated_at=utc_now(),
            )
            self._sessions[saved.session_id] = copy_session(saved)
            return copy_session(saved)

    def get_or_create(
        self,
        session_id: str | None = None,
        locale: str = "zh-CN",
    ) -> AgentSession:
        """存在则返回现有 session，否则创建新 session。"""
        if session_id:
            existing = self.get(session_id)
            if existing is not None:
                return existing
        return self.create(session_id=session_id, locale=locale)


def copy_session(session: AgentSession) -> AgentSession:
    """构造 Session 快照，避免 Store 暴露内部可变对象。"""

    return AgentSession(
        session_id=session.session_id,
        status=session.status,
        messages=_copy_messages(session.messages),
        pending_action_id=session.pending_action_id,
        continuation=session.continuation,
        active_run_id=session.active_run_id,
        run_fence_generation=session.run_fence_generation,
        active_run_last_heartbeat_at=session.active_run_last_heartbeat_at,
        active_run_lease_expires_at=session.active_run_lease_expires_at,
        version=session.version,
        created_at=session.created_at,
        updated_at=session.updated_at,
        current_skill=session.current_skill,
        turns=session.turns,
        pending_confirmations=list(session.pending_confirmations),
        context_summary=session.context_summary,
        locale=session.locale,
    )


def _copy_messages(messages: list[ModelMessage] | tuple[ModelMessage, ...]) -> list[ModelMessage]:
    return [_copy_message(message) for message in messages or []]


def _copy_message(message: ModelMessage) -> ModelMessage:
    tool_calls = tuple(_copy_tool_call(call) for call in tuple(message.tool_calls or ()))
    return ModelMessage(
        role=message.role,
        content=message.content,
        name=message.name,
        tool_call_id=message.tool_call_id,
        tool_calls=tool_calls,
    )


def _copy_tool_call(tool_call: ModelToolCall) -> ModelToolCall:
    return ModelToolCall(
        id=tool_call.id,
        name=tool_call.name,
        raw_arguments=tool_call.raw_arguments,
        arguments=mutable_mapping(tool_call.arguments),
    )


def _coerce_session_status(value: AgentSessionStatus | RunStatus | str) -> AgentSessionStatus:
    if isinstance(value, RunStatus):
        if value == RunStatus.PENDING:
            return AgentSessionStatus.ACTIVE
        if value == RunStatus.RUNNING:
            return AgentSessionStatus.RUNNING
        if value == RunStatus.WAITING_CONFIRMATION:
            return AgentSessionStatus.WAITING_CONFIRMATION
        if value == RunStatus.COMPLETED:
            return AgentSessionStatus.COMPLETED
        if value == RunStatus.FAILED:
            return AgentSessionStatus.FAILED
    try:
        return AgentSessionStatus(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported session status: {value!r}") from exc


def _require_aware_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _optional_aware_utc(value: datetime | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    return _require_aware_utc(value, field_name)
