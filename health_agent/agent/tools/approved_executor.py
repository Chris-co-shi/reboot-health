"""已确认 Tool Action 的受控执行入口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from agent.runtime.pending_action import (
    PendingActionStatus,
    calculate_arguments_hash,
)
from agent.runtime.pending_action_store import PendingActionStore
from agent.tools.contract import (
    ToolExecutionResult,
    ToolPermission,
    error_content,
    success_content,
)
from agent.tools.executor import INVALID_TOOL_RESULT, TOOL_EXECUTION_FAILED
from agent.tools.registry import ToolRegistry

CONFIRMATION_ACTION_NOT_FOUND = "confirmation_action_not_found"
CONFIRMATION_ARGUMENTS_HASH_MISMATCH = "confirmation_arguments_hash_mismatch"
CONFIRMATION_TOOL_NOT_FOUND = "confirmation_tool_not_found"
CONFIRMATION_PERMISSION_CHANGED = "confirmation_permission_changed"
TOOL_EXECUTION_STATE_UNKNOWN = "tool_execution_state_unknown"


@dataclass(frozen=True)
class ApprovedActionExecutionError(RuntimeError):
    """ApprovedActionExecutor 的安全失败。

    这些错误表示 Runtime 绑定或权限边界不可信，不伪装成业务 Tool Result，也不
    调用 handler。
    """

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


class ApprovedActionExecutor:
    """执行已经进入 EXECUTING 状态的 confirmation-required Action。

    入口只接收 action_id。tool_name、arguments 和 tool_call_id 均从
    PendingActionStore 中读取，调用方没有机会替换参数。
    """

    def __init__(
        self,
        *,
        pending_action_store: PendingActionStore,
        tool_registry: ToolRegistry,
    ) -> None:
        self.pending_action_store = pending_action_store
        self.tool_registry = tool_registry

    def execute(self, action_id: str) -> ToolExecutionResult:
        """执行一次已确认 Action。

        若 Action 状态、hash 或 Tool 权限不可信，抛出安全错误并保持 handler
        未调用。handler 自身异常会被转换为结构化 Tool Error。
        """

        normalized_action_id = str(action_id or "").strip()
        if not normalized_action_id:
            raise ApprovedActionExecutionError(
                code=CONFIRMATION_ACTION_NOT_FOUND,
                message="Pending action id is required",
            )
        action = self.pending_action_store.get(normalized_action_id)
        if action is None:
            raise ApprovedActionExecutionError(
                code=CONFIRMATION_ACTION_NOT_FOUND,
                message="Pending action was not found",
            )
        if action.status != PendingActionStatus.EXECUTING:
            raise ApprovedActionExecutionError(
                code=TOOL_EXECUTION_STATE_UNKNOWN,
                message="Pending action is not in EXECUTING state",
            )
        if calculate_arguments_hash(action.arguments) != action.arguments_hash:
            raise ApprovedActionExecutionError(
                code=CONFIRMATION_ARGUMENTS_HASH_MISMATCH,
                message="Pending action arguments hash does not match",
            )

        definition = self.tool_registry.get(action.tool_name)
        if definition is None:
            raise ApprovedActionExecutionError(
                code=CONFIRMATION_TOOL_NOT_FOUND,
                message="Tool definition was not found",
            )
        if definition.permission != ToolPermission.CONFIRMATION_REQUIRED:
            raise ApprovedActionExecutionError(
                code=CONFIRMATION_PERMISSION_CHANGED,
                message="Tool permission changed before confirmed execution",
            )

        try:
            result = definition.handler(action.arguments)
        except Exception:
            return _tool_error(
                tool_call_id=action.tool_call_id,
                tool_name=action.tool_name,
                code=TOOL_EXECUTION_FAILED,
                message="Tool execution failed",
            )
        if not isinstance(result, Mapping):
            return _tool_error(
                tool_call_id=action.tool_call_id,
                tool_name=action.tool_name,
                code=INVALID_TOOL_RESULT,
                message="Tool result must be a JSON object",
            )
        try:
            content = success_content(result)
        except (TypeError, ValueError):
            return _tool_error(
                tool_call_id=action.tool_call_id,
                tool_name=action.tool_name,
                code=INVALID_TOOL_RESULT,
                message="Tool result must be JSON serializable",
            )
        return ToolExecutionResult(
            tool_call_id=action.tool_call_id,
            tool_name=action.tool_name,
            success=True,
            content=content,
        )


def _tool_error(
    *,
    tool_call_id: str,
    tool_name: str,
    code: str,
    message: str,
) -> ToolExecutionResult:
    """构造可保存和回放的 Tool Error。"""

    return ToolExecutionResult(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        success=False,
        content=error_content(code, message),
        error_code=code,
    )
