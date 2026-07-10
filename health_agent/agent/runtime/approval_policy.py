"""Tool ApprovalPolicy。

本模块只做确定性权限决策，不查 Registry、不校验参数、不执行 Tool，也不创建
PendingAction。调用方必须依据 enum 字段做流程控制，不得解析 message 文本。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from agent.tools.contract import ToolDefinition, ToolPermission


class ToolDisposition(StrEnum):
    """ApprovalPolicy 对一次 Tool Call 的流程处置。"""

    EXECUTE_NOW = "execute_now"
    REQUIRE_CONFIRMATION = "require_confirmation"
    DENY = "deny"


class ToolPolicyReason(StrEnum):
    """稳定、可测试的 ToolPolicyDecision 原因码。"""

    READ_ONLY_ALLOWED = "read_only_allowed"
    USER_CONFIRMATION_REQUIRED = "user_confirmation_required"
    TOOL_NOT_FOUND = "tool_not_found"
    UNSUPPORTED_PERMISSION = "unsupported_permission"


@dataclass(frozen=True)
class ToolPolicyDecision:
    """ApprovalPolicy 的不可变决策结果。

    `message` 只允许承载安全摘要，不得包含完整 arguments、健康原文或凭据。
    Runtime 逻辑只能依赖 `disposition` 和 `reason`。
    """

    disposition: ToolDisposition
    reason: ToolPolicyReason
    message: str

    def __post_init__(self) -> None:
        message = str(self.message or "").strip()
        if not message:
            raise ValueError("ToolPolicyDecision message must not be empty")
        object.__setattr__(self, "disposition", ToolDisposition(self.disposition))
        object.__setattr__(self, "reason", ToolPolicyReason(self.reason))
        object.__setattr__(self, "message", message)


class ApprovalPolicy:
    """无状态 Tool 批准策略。

    当前策略只读取 ToolDefinition.permission。参数是否合法、是否应冻结成
    PendingAction、以及用户确认后的恢复执行，都属于后续 Slice。
    """

    def evaluate(self, tool_definition: ToolDefinition | None) -> ToolPolicyDecision:
        """根据 ToolDefinition 返回确定性处置。"""

        if tool_definition is None:
            return ToolPolicyDecision(
                disposition=ToolDisposition.DENY,
                reason=ToolPolicyReason.TOOL_NOT_FOUND,
                message="Tool is not registered",
            )

        permission = _tool_permission(tool_definition)
        if permission == ToolPermission.READ_ONLY:
            return ToolPolicyDecision(
                disposition=ToolDisposition.EXECUTE_NOW,
                reason=ToolPolicyReason.READ_ONLY_ALLOWED,
                message="Read-only tool may execute immediately",
            )
        if permission == ToolPermission.CONFIRMATION_REQUIRED:
            return ToolPolicyDecision(
                disposition=ToolDisposition.REQUIRE_CONFIRMATION,
                reason=ToolPolicyReason.USER_CONFIRMATION_REQUIRED,
                message="Tool requires user confirmation",
            )
        return ToolPolicyDecision(
            disposition=ToolDisposition.DENY,
            reason=ToolPolicyReason.UNSUPPORTED_PERMISSION,
            message="Tool permission is not supported",
        )


def _tool_permission(tool_definition: ToolDefinition) -> Any:
    """读取 permission 时不触碰 handler，保留防御性 unsupported 分支。"""

    return getattr(tool_definition, "permission", None)
