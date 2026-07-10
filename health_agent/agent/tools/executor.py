"""Tool Executor 强制执行边界。"""

from __future__ import annotations

from typing import Any, Mapping

from agent.models import ModelToolCall
from agent.tools.contract import (
    ToolArgumentError,
    ToolExecutionResult,
    ToolPermission,
    error_content,
    success_content,
)
from agent.tools.registry import ToolRegistry

UNKNOWN_TOOL = "unknown_tool"
INVALID_ARGUMENTS = "invalid_arguments"
FORBIDDEN_TOOL = "forbidden_tool"
TOOL_CONFIRMATION_REQUIRED = "tool_confirmation_required"
TOOL_EXECUTION_FAILED = "tool_execution_failed"
INVALID_TOOL_RESULT = "invalid_tool_result"


class ToolExecutor:
    """执行已注册 Tool 的普通入口。

    本入口没有“已确认后执行”能力，也没有 bypass 参数。即使调用方绕过
    ApprovalPolicy 直接调用 Executor，`CONFIRMATION_REQUIRED` Tool 也只能得到
    结构化确认错误，handler 绝不会被调用。
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(self, tool_call: ModelToolCall) -> ToolExecutionResult:
        """执行一次 ModelToolCall 并返回可回送给模型的 JSON 结果。"""
        definition = self.registry.get(tool_call.name)
        if definition is None:
            return self._error(
                tool_call=tool_call,
                code=UNKNOWN_TOOL,
                message=f"Unknown tool: {tool_call.name}",
            )

        try:
            arguments = definition.validate_arguments(tool_call.arguments)
        except (ToolArgumentError, TypeError, ValueError) as exc:
            return self._error(
                tool_call=tool_call,
                code=INVALID_ARGUMENTS,
                message=_safe_argument_error_message(exc),
            )

        # 未来 GenericAgentLoop 接入顺序应保持：
        # registry lookup -> argument validation -> ApprovalPolicy -> execute/pause。
        # Executor 仍重复检查 permission，作为调用方绕过 Policy 时的第二道边界。
        if definition.permission == ToolPermission.CONFIRMATION_REQUIRED:
            return self._error(
                tool_call=tool_call,
                code=TOOL_CONFIRMATION_REQUIRED,
                message="Tool requires user confirmation before execution",
            )
        if definition.permission != ToolPermission.READ_ONLY:
            return self._error(
                tool_call=tool_call,
                code=FORBIDDEN_TOOL,
                message="Tool permission is not supported by this executor",
            )

        try:
            result = definition.handler(arguments)
        except Exception:
            return self._error(
                tool_call=tool_call,
                code=TOOL_EXECUTION_FAILED,
                message="Tool execution failed",
            )

        if not isinstance(result, Mapping):
            return self._error(
                tool_call=tool_call,
                code=INVALID_TOOL_RESULT,
                message="Tool result must be a JSON object",
            )

        try:
            content = success_content(result)
        except (TypeError, ValueError):
            return self._error(
                tool_call=tool_call,
                code=INVALID_TOOL_RESULT,
                message="Tool result must be JSON serializable",
            )

        return ToolExecutionResult(
            tool_call_id=tool_call.id,
            tool_name=definition.name,
            success=True,
            content=content,
        )

    def _error(
        self,
        tool_call: ModelToolCall,
        code: str,
        message: str,
    ) -> ToolExecutionResult:
        """构造失败 ToolExecutionResult。"""
        return ToolExecutionResult(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            success=False,
            content=error_content(code, message),
            error_code=code,
        )


def _safe_argument_error_message(exc: Exception) -> str:
    """参数错误可以给模型，但仍限制长度和换行。"""
    text = str(exc).strip() or "Invalid tool arguments"
    return " ".join(text.split())[:200]
