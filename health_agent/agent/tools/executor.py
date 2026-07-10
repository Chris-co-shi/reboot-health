"""只读 Tool Executor。"""

from __future__ import annotations

from typing import Any, Mapping

from agent.models import ModelToolCall
from agent.tools.contract import (
    ToolArgumentError,
    ToolExecutionResult,
    ToolPermission,
    ToolSideEffect,
    error_content,
    success_content,
)
from agent.tools.registry import ToolRegistry

UNKNOWN_TOOL = "unknown_tool"
INVALID_ARGUMENTS = "invalid_arguments"
FORBIDDEN_TOOL = "forbidden_tool"
TOOL_EXECUTION_FAILED = "tool_execution_failed"
INVALID_TOOL_RESULT = "invalid_tool_result"


class ToolExecutor:
    """执行已注册的只读无副作用 Tool。"""

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

        if (
            definition.permission != ToolPermission.READ_ONLY
            or definition.side_effect != ToolSideEffect.NONE
        ):
            return self._error(
                tool_call=tool_call,
                code=FORBIDDEN_TOOL,
                message="Tool is not allowed in the read-only runtime",
            )

        try:
            arguments = definition.validate_arguments(tool_call.arguments)
        except (ToolArgumentError, TypeError, ValueError) as exc:
            return self._error(
                tool_call=tool_call,
                code=INVALID_ARGUMENTS,
                message=_safe_argument_error_message(exc),
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
