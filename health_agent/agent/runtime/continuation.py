"""Agent 执行续点合同。

本模块只描述暂停后恢复所需的通用运行位置，不执行 Resume。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class AgentContinuation:
    """一次暂停运行的续点。

    `next_tool_call_index` 表示 Resume 后下一条尚未执行的 Tool Call 索引。
    """

    originating_run_id: str
    assistant_message_index: int
    next_tool_call_index: int
    model_turns_used: int
    tool_calls_used: int
    started_at: datetime
    deadline_at: datetime

    def __post_init__(self) -> None:
        originating_run_id = str(self.originating_run_id or "").strip()
        if not originating_run_id:
            raise ValueError("originating_run_id must not be empty")
        object.__setattr__(self, "originating_run_id", originating_run_id)

        for field_name in (
            "assistant_message_index",
            "next_tool_call_index",
            "model_turns_used",
            "tool_calls_used",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")

        started_at = _require_aware_utc(self.started_at, "started_at")
        deadline_at = _require_aware_utc(self.deadline_at, "deadline_at")
        if deadline_at < started_at:
            raise ValueError("deadline_at must not be earlier than started_at")
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "deadline_at", deadline_at)


def _require_aware_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)
