"""Tool Executor 强制执行边界。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from agent.models import ModelToolCall
from agent.models.base import freeze_mapping
from agent.tools.contract import (
    ToolArgumentError,
    ToolDefinition,
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


@dataclass(frozen=True)
class PreparedToolCall:
    """经过 Registry lookup 与参数校验后的 Tool Call 快照。

    Prepared 只表示「工具存在且参数合法」，不表示「可以执行」。调用方仍必须
    经过 ApprovalPolicy，Executor 在执行前也会再次检查 permission。
    """

    tool_call_id: str
    tool_name: str
    definition: ToolDefinition
    arguments: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", freeze_mapping(self.arguments))


@dataclass(frozen=True)
class ToolPreflightResult:
    """Tool preflight 的二选一结果。

    成功时只有 `prepared_call`；失败时只有 `error_result`。错误结果沿用
    ToolExecutionResult，确保未知工具、非法 JSON 和 validator 失败都用同一种
    role=tool 结构返回模型。
    """

    prepared_call: PreparedToolCall | None = None
    error_result: ToolExecutionResult | None = None

    def __post_init__(self) -> None:
        has_prepared = self.prepared_call is not None
        has_error = self.error_result is not None
        if has_prepared == has_error:
            raise ValueError("ToolPreflightResult must contain exactly one result")

    @property
    def is_valid(self) -> bool:
        """是否已得到可交给 ApprovalPolicy 判断的合法 Tool Call。"""

        return self.prepared_call is not None


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
        preflight = self.preflight(tool_call)
        if preflight.error_result is not None:
            return preflight.error_result
        prepared_call = preflight.prepared_call
        if prepared_call is None:
            raise RuntimeError("Tool preflight returned no prepared call")
        return self.execute_prepared(prepared_call)

    def preflight(self, tool_call: ModelToolCall) -> ToolPreflightResult:
        """只做查找和参数校验，不调用 handler。

        未来暂停确认流程依赖此方法生成可冻结的合法参数快照。这里有意不调用
        ApprovalPolicy，也不判断用户确认状态，避免 Tool Runtime 与 Session 状态
        互相耦合。
        """
        definition = self.registry.get(tool_call.name)
        if definition is None:
            return ToolPreflightResult(
                error_result=self._error(
                    tool_call=tool_call,
                    code=UNKNOWN_TOOL,
                    message=f"Unknown tool: {tool_call.name}",
                )
            )

        raw_error = _raw_arguments_error(tool_call.raw_arguments)
        if raw_error is not None:
            return ToolPreflightResult(
                error_result=self._error(
                    tool_call=tool_call,
                    code=INVALID_ARGUMENTS,
                    message=raw_error,
                )
            )

        try:
            arguments = definition.validate_arguments(tool_call.arguments)
        except (ToolArgumentError, TypeError, ValueError) as exc:
            return ToolPreflightResult(
                error_result=self._error(
                    tool_call=tool_call,
                    code=INVALID_ARGUMENTS,
                    message=_safe_argument_error_message(exc),
                )
            )

        return ToolPreflightResult(
            prepared_call=PreparedToolCall(
                tool_call_id=tool_call.id,
                tool_name=definition.name,
                definition=definition,
                arguments=arguments,
            )
        )

    def execute_prepared(self, prepared_call: PreparedToolCall) -> ToolExecutionResult:
        """执行已通过 preflight 的 READ_ONLY Tool。

        这不是批准后执行入口；它只服务于已确认 `READ_ONLY` 的普通执行路径。即使
        外部传入 confirmation-required PreparedToolCall，也会在这里再次被阻断。
        """
        definition = prepared_call.definition
        if definition.permission == ToolPermission.CONFIRMATION_REQUIRED:
            return self._error_from_parts(
                tool_call_id=prepared_call.tool_call_id,
                tool_name=prepared_call.tool_name,
                code=TOOL_CONFIRMATION_REQUIRED,
                message="Tool requires user confirmation before execution",
            )
        if definition.permission != ToolPermission.READ_ONLY:
            return self._error_from_parts(
                tool_call_id=prepared_call.tool_call_id,
                tool_name=prepared_call.tool_name,
                code=FORBIDDEN_TOOL,
                message="Tool permission is not supported by this executor",
            )

        try:
            result = definition.handler(prepared_call.arguments)
        except Exception:
            return self._error_from_parts(
                tool_call_id=prepared_call.tool_call_id,
                tool_name=prepared_call.tool_name,
                code=TOOL_EXECUTION_FAILED,
                message="Tool execution failed",
            )

        if not isinstance(result, Mapping):
            return self._error_from_parts(
                tool_call_id=prepared_call.tool_call_id,
                tool_name=prepared_call.tool_name,
                code=INVALID_TOOL_RESULT,
                message="Tool result must be a JSON object",
            )

        try:
            content = success_content(result)
        except (TypeError, ValueError):
            return self._error_from_parts(
                tool_call_id=prepared_call.tool_call_id,
                tool_name=prepared_call.tool_name,
                code=INVALID_TOOL_RESULT,
                message="Tool result must be JSON serializable",
            )

        return ToolExecutionResult(
            tool_call_id=prepared_call.tool_call_id,
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
        return self._error_from_parts(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            code=code,
            message=message,
        )

    def _error_from_parts(
        self,
        tool_call_id: str,
        tool_name: str,
        code: str,
        message: str,
    ) -> ToolExecutionResult:
        """按基础字段构造失败 ToolExecutionResult。"""
        return ToolExecutionResult(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            success=False,
            content=error_content(code, message),
            error_code=code,
        )


def _raw_arguments_error(raw_arguments: str) -> str | None:
    """验证 raw_arguments 形状，用于拦截测试或 Provider 之外构造的非法 Tool Call。"""

    raw = str(raw_arguments or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return "Tool arguments must be valid JSON"
    if not isinstance(parsed, Mapping):
        return "Tool arguments must be a JSON object"
    return None


def _safe_argument_error_message(exc: Exception) -> str:
    """参数错误可以给模型，但仍限制长度和换行。"""
    text = str(exc).strip() or "Invalid tool arguments"
    return " ".join(text.split())[:200]
