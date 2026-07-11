"""RUNNING Session 的 durable execution checkpoint 合同。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class RunExecutionCheckpointPhase(StrEnum):
    """可恢复运行在最近一次持久化时所处的外部调用阶段。"""

    DRIVE_READY = "drive_ready"
    MODEL_CALL_IN_FLIGHT = "model_call_in_flight"
    TOOL_CALL_IN_FLIGHT = "tool_call_in_flight"
    FINALIZING = "finalizing"


@dataclass(frozen=True)
class RunExecutionCheckpoint:
    """当前 RUNNING run 的可恢复游标。

    该对象只描述执行位置和预算，不保存消息内容、Tool arguments、Provider 响应或
    任何认证信息。`run_fence_generation` 让 checkpoint 与 owner generation 绑定，
    防止 stale owner 在恢复后继续写旧快照。
    """

    checkpoint_phase: RunExecutionCheckpointPhase
    originating_run_id: str
    run_fence_generation: int
    assistant_message_index: int | None
    next_tool_call_index: int
    current_tool_call_id: str | None
    current_tool_name: str | None
    model_turns_used: int
    tool_calls_used: int
    remaining_runtime_seconds: float
    started_at: datetime
    deadline_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        phase = RunExecutionCheckpointPhase(self.checkpoint_phase)
        object.__setattr__(self, "checkpoint_phase", phase)

        originating_run_id = str(self.originating_run_id or "").strip()
        if not originating_run_id:
            raise ValueError("originating_run_id must not be empty")
        object.__setattr__(self, "originating_run_id", originating_run_id)

        if not isinstance(self.run_fence_generation, int) or self.run_fence_generation <= 0:
            raise ValueError("run_fence_generation must be a positive integer")

        if self.assistant_message_index is not None:
            if (
                not isinstance(self.assistant_message_index, int)
                or self.assistant_message_index < 0
            ):
                raise ValueError("assistant_message_index must be a non-negative integer")
        for field_name in (
            "next_tool_call_index",
            "model_turns_used",
            "tool_calls_used",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")

        current_tool_call_id = _optional_non_empty_string(
            self.current_tool_call_id,
            "current_tool_call_id",
        )
        current_tool_name = _optional_non_empty_string(
            self.current_tool_name,
            "current_tool_name",
        )
        if bool(current_tool_call_id) != bool(current_tool_name):
            raise ValueError("current tool id and name must be present together")
        if phase == RunExecutionCheckpointPhase.TOOL_CALL_IN_FLIGHT:
            if current_tool_call_id is None:
                raise ValueError("TOOL_CALL_IN_FLIGHT must include current tool")
        elif current_tool_call_id is not None:
            raise ValueError("current tool is only valid during TOOL_CALL_IN_FLIGHT")
        object.__setattr__(self, "current_tool_call_id", current_tool_call_id)
        object.__setattr__(self, "current_tool_name", current_tool_name)

        try:
            remaining_runtime_seconds = float(self.remaining_runtime_seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError("remaining_runtime_seconds must be non-negative") from exc
        if remaining_runtime_seconds < 0:
            raise ValueError("remaining_runtime_seconds must be non-negative")
        object.__setattr__(
            self,
            "remaining_runtime_seconds",
            remaining_runtime_seconds,
        )

        started_at = _require_aware_utc(self.started_at, "started_at")
        deadline_at = _require_aware_utc(self.deadline_at, "deadline_at")
        updated_at = _require_aware_utc(self.updated_at, "updated_at")
        if deadline_at < started_at:
            raise ValueError("deadline_at must not be earlier than started_at")
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "deadline_at", deadline_at)
        object.__setattr__(self, "updated_at", updated_at)


def _optional_non_empty_string(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _require_aware_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)
