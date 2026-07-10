"""PendingAction 合同和状态转换。

PendingAction 保存的是模型 Tool Call 的确定性快照；本模块不执行 Tool，
也不判断权限或过期策略。
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from agent.models.base import freeze_mapping, mutable_mapping

DEFAULT_PENDING_ACTION_TTL = timedelta(minutes=15)


class PendingActionStatus(StrEnum):
    """PendingAction 生命周期。"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"


class PendingActionTransitionError(ValueError):
    """PendingAction 状态转换不合法。"""


def utc_now() -> datetime:
    """返回 UTC aware 当前时间。"""

    return datetime.now(UTC)


def default_expires_at() -> datetime:
    """返回默认过期时间。"""

    return utc_now() + DEFAULT_PENDING_ACTION_TTL


_ALLOWED_TRANSITIONS = {
    PendingActionStatus.PENDING: {
        PendingActionStatus.APPROVED,
        PendingActionStatus.REJECTED,
        PendingActionStatus.EXPIRED,
    },
    PendingActionStatus.APPROVED: {PendingActionStatus.EXECUTING},
    PendingActionStatus.EXECUTING: {
        PendingActionStatus.EXECUTED,
        PendingActionStatus.FAILED,
    },
}


@dataclass(frozen=True)
class PendingAction:
    """等待用户确认的一次 Tool Call 快照。"""

    action_id: str
    session_id: str
    originating_run_id: str
    tool_call_id: str
    tool_name: str
    arguments: Mapping[str, Any]
    assistant_message_index: int
    tool_call_index: int
    summary: str
    expires_at: datetime
    arguments_hash: str = ""
    status: PendingActionStatus = PendingActionStatus.PENDING
    idempotency_key: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    version: int = 0

    def __post_init__(self) -> None:
        for field_name in (
            "action_id",
            "session_id",
            "originating_run_id",
            "tool_call_id",
            "tool_name",
        ):
            normalized = str(getattr(self, field_name) or "").strip()
            if not normalized:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, normalized)

        if not isinstance(self.assistant_message_index, int) or self.assistant_message_index < 0:
            raise ValueError("assistant_message_index must be a non-negative integer")
        if not isinstance(self.tool_call_index, int) or self.tool_call_index < 0:
            raise ValueError("tool_call_index must be a non-negative integer")
        if not isinstance(self.version, int) or self.version < 0:
            raise ValueError("version must be a non-negative integer")

        summary = str(self.summary or "").strip()
        if not summary:
            raise ValueError("summary must not be empty")
        object.__setattr__(self, "summary", summary)

        created_at = _require_aware_utc(self.created_at, "created_at")
        updated_at = _require_aware_utc(self.updated_at, "updated_at")
        expires_at = _require_aware_utc(self.expires_at, "expires_at")
        if updated_at < created_at:
            raise ValueError("updated_at must not be earlier than created_at")
        if expires_at <= created_at:
            raise ValueError("expires_at must be later than created_at")
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)
        object.__setattr__(self, "expires_at", expires_at)

        arguments_snapshot = _freeze_json_arguments(self.arguments)
        object.__setattr__(self, "arguments", arguments_snapshot)

        calculated_hash = calculate_arguments_hash(arguments_snapshot)
        if self.arguments_hash and self.arguments_hash != calculated_hash:
            raise ValueError("arguments_hash does not match arguments")
        object.__setattr__(self, "arguments_hash", calculated_hash)

        try:
            status = PendingActionStatus(self.status)
        except ValueError as exc:
            raise ValueError(f"Unsupported pending action status: {self.status!r}") from exc
        object.__setattr__(self, "status", status)

        idempotency_key = str(self.idempotency_key or "").strip()
        if not idempotency_key:
            idempotency_key = f"pending-action:{self.action_id}"
        object.__setattr__(self, "idempotency_key", idempotency_key)


def canonicalize_tool_arguments(arguments: Mapping[str, Any]) -> str:
    """返回 Tool arguments 的确定性 JSON 文本。"""

    canonical = _to_json_value(arguments)
    if not isinstance(canonical, dict):
        raise ValueError("tool arguments must be a JSON object")
    return json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def calculate_arguments_hash(arguments: Mapping[str, Any]) -> str:
    """使用规范化 JSON 和 SHA-256 计算参数 hash。"""

    canonical = canonicalize_tool_arguments(arguments)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def transition_pending_action(
    action: PendingAction,
    new_status: PendingActionStatus,
    *,
    now: datetime | None = None,
) -> PendingAction:
    """返回状态转换后的新 PendingAction。"""

    status = PendingActionStatus(new_status)
    allowed = _ALLOWED_TRANSITIONS.get(action.status, set())
    if status not in allowed:
        raise PendingActionTransitionError(
            f"Cannot transition pending action from {action.status} to {status}"
        )
    updated_at = _require_aware_utc(now, "now") if now is not None else utc_now()
    return replace(action, status=status, updated_at=updated_at)


def copy_pending_action(action: PendingAction) -> PendingAction:
    """构造 PendingAction 快照，避免暴露内部可变引用。"""

    return PendingAction(
        action_id=action.action_id,
        session_id=action.session_id,
        originating_run_id=action.originating_run_id,
        tool_call_id=action.tool_call_id,
        tool_name=action.tool_name,
        arguments=mutable_mapping(action.arguments),
        assistant_message_index=action.assistant_message_index,
        tool_call_index=action.tool_call_index,
        summary=action.summary,
        expires_at=action.expires_at,
        arguments_hash=action.arguments_hash,
        status=action.status,
        idempotency_key=action.idempotency_key,
        created_at=action.created_at,
        updated_at=action.updated_at,
        version=action.version,
    )


def _freeze_json_arguments(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    value = _to_json_value(arguments)
    if not isinstance(value, dict):
        raise ValueError("tool arguments must be a JSON object")
    return freeze_mapping(value)


def _to_json_value(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        value = dict(value)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("tool argument object keys must be strings")
            result[key] = _to_json_value(item)
        return result
    if isinstance(value, list | tuple):
        return [_to_json_value(item) for item in value]
    if isinstance(value, str) or value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("tool arguments must not contain NaN or Infinity")
        return value
    raise ValueError(f"tool arguments contain non-JSON value: {type(value).__name__}")


def _require_aware_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)
