"""用户确认决策合同与安全结果。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from agent.runtime.result import AgentRunError

MAX_CONFIRMATION_REASON_CHARS = 200


class ConfirmationDecisionType(StrEnum):
    """用户对 PendingAction 的唯一允许决策。"""

    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True)
class ConfirmationDecision:
    """一次用户确认命令。

    本合同只允许“原样批准”或“拒绝”。它不包含 Tool 参数字段，也不允许调用方
    通过 decision 命令替换模型产生并已冻结的 arguments。
    """

    session_id: str
    action_id: str
    decision: ConfirmationDecisionType
    reason: str | None = None

    def __post_init__(self) -> None:
        session_id = str(self.session_id or "").strip()
        if not session_id:
            raise ValueError("session_id must not be empty")
        object.__setattr__(self, "session_id", session_id)

        action_id = str(self.action_id or "").strip()
        if not action_id:
            raise ValueError("action_id must not be empty")
        object.__setattr__(self, "action_id", action_id)

        if not isinstance(self.decision, ConfirmationDecisionType):
            raise ValueError("decision must be a ConfirmationDecisionType")

        reason = _normalize_reason(self.reason)
        object.__setattr__(self, "reason", reason)


class ConfirmationResolutionStatus(StrEnum):
    """确认处理的外部安全状态。"""

    RESOLVED = "confirmation_resolved"
    REJECTED = "confirmation_rejected"
    EXPIRED = "confirmation_expired"
    CONFLICT = "confirmation_conflict"
    FAILED = "failed"


@dataclass(frozen=True)
class ConfirmationResolutionResult:
    """确认处理结果摘要。

    该结果明确表示“当前确认已处理或失败”，不伪装成最终 Agent 回答，也不包含
    arguments、arguments_hash、idempotency_key、Store version 或完整内部结果。
    """

    status: ConfirmationResolutionStatus
    session_id: str
    action_id: str
    tool_name: str | None
    decision: ConfirmationDecisionType
    tool_succeeded: bool | None = None
    error: AgentRunError | None = None
    model_turns_used: int | None = None
    tool_calls_used: int | None = None
    next_tool_call_index: int | None = None
    remaining_runtime_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """返回 API/CLI 友好的安全结构。"""

        return {
            "status": self.status.value,
            "sessionId": self.session_id,
            "actionId": self.action_id,
            "toolName": self.tool_name,
            "decision": self.decision.value,
            "toolSucceeded": self.tool_succeeded,
            "error": self.error.to_dict() if self.error else None,
            "modelTurnsUsed": self.model_turns_used,
            "toolCallsUsed": self.tool_calls_used,
            "nextToolCallIndex": self.next_tool_call_index,
            "remainingRuntimeSeconds": self.remaining_runtime_seconds,
        }


def _normalize_reason(value: str | None) -> str | None:
    """规范化可选 reason；它只可内部保存，不回显到 Tool Result。"""

    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if len(text) > MAX_CONFIRMATION_REASON_CHARS:
        raise ValueError("reason is too long")
    return text or None
