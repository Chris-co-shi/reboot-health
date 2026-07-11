"""Agent 执行续点合同。

本模块只描述暂停后恢复所需的通用运行位置，不执行 Resume。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class AgentContinuation:
    """一次暂停运行的续点。

    `next_tool_call_index` 表示 Resume 后下一条尚未执行的 Tool Call 索引。

    该数据结构用于在 Agent 执行被中断后，能够准确地从断点处恢复执行。
    记录了所有必要的状态信息，包括已使用的模型回合数、工具调用次数等，
    以确保恢复后的执行不会超出预设的限制。
    """

    # 原始运行的唯一标识符，用于关联到被中断的执行实例
    originating_run_id: str

    # 助手消息在消息历史中的索引位置，标识需要恢复的具体对话轮次
    assistant_message_index: int

    # 下一个待执行的 Tool Call 的索引，Resume 后将从此索引开始执行
    next_tool_call_index: int

    # 已使用的模型调用回合数，用于继续追踪是否达到最大限制
    model_turns_used: int

    # 已使用的工具调用次数，用于继续追踪是否达到最大限制
    tool_calls_used: int

    # 原始运行开始的时间戳（UTC），用于计算剩余时间
    started_at: datetime

    # 原始运行的截止时间戳（UTC），只保留为诊断信息；人工确认等待不消耗此预算
    deadline_at: datetime

    # 暂停瞬间剩余的 active runtime 秒数；Slice 4B 恢复时会以恢复时间重新计算截止点
    remaining_runtime_seconds: float | None = None

    def __post_init__(self) -> None:
        """数据验证和标准化处理。

        在数据类初始化后立即执行，确保所有字段的值符合业务约束：
        - originating_run_id 必须是非空字符串
        - 所有计数字段必须是非负整数
        - 时间字段必须是带时区的 UTC 时间
        - 截止时间不能早于开始时间
        """
        # 验证并标准化 originating_run_id：去除首尾空格并确保非空
        originating_run_id = str(self.originating_run_id or "").strip()
        if not originating_run_id:
            raise ValueError("originating_run_id must not be empty")
        object.__setattr__(self, "originating_run_id", originating_run_id)

        # 验证所有计数字段必须是非负整数
        for field_name in (
            "assistant_message_index",
            "next_tool_call_index",
            "model_turns_used",
            "tool_calls_used",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")

        # 验证并转换时间字段为 UTC 时区
        started_at = _require_aware_utc(self.started_at, "started_at")
        deadline_at = _require_aware_utc(self.deadline_at, "deadline_at")

        # 确保截止时间不早于开始时间
        if deadline_at < started_at:
            raise ValueError("deadline_at must not be earlier than started_at")

        remaining_runtime_seconds = _coerce_remaining_runtime_seconds(
            self.remaining_runtime_seconds,
            started_at=started_at,
            deadline_at=deadline_at,
        )

        # 由于是 frozen dataclass，使用 object.__setattr__ 更新字段值
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "deadline_at", deadline_at)
        object.__setattr__(
            self,
            "remaining_runtime_seconds",
            remaining_runtime_seconds,
        )


def _require_aware_utc(value: datetime, field_name: str) -> datetime:
    """确保 datetime 值是带时区信息的 UTC 时间。

    Args:
        value: 需要验证和转换的 datetime 对象
        field_name: 字段名称，用于错误提示信息

    Returns:
        转换为 UTC 时区的 datetime 对象

    Raises:
        ValueError: 如果值不是 datetime 类型或缺少时区信息
    """
    # 验证输入必须是 datetime 类型
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")

    # 验证必须包含时区信息（tzinfo 不为 None 且 utcoffset 不为 None）
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")

    # 统一转换为 UTC 时区，确保时间比较和计算的一致性
    return value.astimezone(UTC)


def _coerce_remaining_runtime_seconds(
    value: Any,
    *,
    started_at: datetime,
    deadline_at: datetime,
) -> float:
    """校验剩余 active runtime 秒数。

    旧 continuation 没有该字段时，按原始 started/deadline 推导，保持历史数据可读。
    新暂停点会显式写入暂停瞬间剩余秒数；用户确认等待期间不会继续递减这个值。
    """

    if value is None:
        return max(0.0, (deadline_at - started_at).total_seconds())
    try:
        remaining = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("remaining_runtime_seconds must be non-negative") from exc
    if remaining < 0:
        raise ValueError("remaining_runtime_seconds must be non-negative")
    return remaining
