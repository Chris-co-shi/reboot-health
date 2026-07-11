"""确认决策协调器。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Callable

from agent.models import ModelMessage, ModelToolCall
from agent.runtime.confirmation import (
    ConfirmationDecision,
    ConfirmationDecisionType,
    ConfirmationResolutionResult,
    ConfirmationResolutionStatus,
)
from agent.runtime.continuation import AgentContinuation
from agent.runtime.pending_action import (
    PendingAction,
    PendingActionStatus,
    calculate_arguments_hash,
    transition_pending_action,
)
from agent.runtime.pending_action_store import (
    PendingActionStore,
    PendingActionStoreError,
)
from agent.runtime.result import AgentRunError
from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    SessionStore,
    SessionStoreError,
)
from agent.tools.approved_executor import (
    ApprovedActionExecutionError,
    ApprovedActionExecutor,
    CONFIRMATION_PERMISSION_CHANGED,
    CONFIRMATION_TOOL_NOT_FOUND,
    TOOL_EXECUTION_STATE_UNKNOWN,
)
from agent.tools.contract import ToolExecutionResult, ToolPermission, error_content
from agent.tools.registry import ToolRegistry

CONFIRMATION_SESSION_NOT_FOUND = "confirmation_session_not_found"
CONFIRMATION_ACTION_NOT_FOUND = "confirmation_action_not_found"
CONFIRMATION_SESSION_MISMATCH = "confirmation_session_mismatch"
CONFIRMATION_CONTINUATION_INVALID = "confirmation_continuation_invalid"
CONFIRMATION_SNAPSHOT_MISMATCH = "confirmation_snapshot_mismatch"
CONFIRMATION_ACTION_EXPIRED = "confirmation_action_expired"
CONFIRMATION_DECISION_CONFLICT = "confirmation_decision_conflict"
CONFIRMATION_ACTION_SAVE_FAILED = "confirmation_action_save_failed"
CONFIRMATION_SESSION_SAVE_FAILED = "confirmation_session_save_failed"
CONFIRMATION_TOOL_RESULT_MISMATCH = "confirmation_tool_result_mismatch"
TOOL_REJECTED_BY_USER = "tool_rejected_by_user"


@dataclass(frozen=True)
class _Binding:
    """一次确认决策所需的内部绑定快照。"""

    session: AgentSession
    action: PendingAction
    continuation: AgentContinuation
    tool_call: ModelToolCall


class ConfirmationCoordinator:
    """处理 WAITING_CONFIRMATION Session 的 Approve/Reject。

    本协调器只消费当前 PendingAction 并保存 role=tool 结果；它不继续后续 Tool
    Calls，也不调用下一轮模型。
    """

    def __init__(
        self,
        *,
        session_store: SessionStore,
        pending_action_store: PendingActionStore,
        tool_registry: ToolRegistry,
        approved_action_executor: ApprovedActionExecutor | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.session_store = session_store
        self.pending_action_store = pending_action_store
        self.tool_registry = tool_registry
        self.approved_action_executor = approved_action_executor or ApprovedActionExecutor(
            pending_action_store=pending_action_store,
            tool_registry=tool_registry,
        )
        self.now_provider = now_provider

    def resolve(self, decision: ConfirmationDecision) -> ConfirmationResolutionResult:
        """应用一次确认决策并返回安全摘要。"""

        session = self.session_store.get(decision.session_id)
        if session is None:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=None,
                code=CONFIRMATION_SESSION_NOT_FOUND,
                message="Session was not found",
            )
        action = self.pending_action_store.get(decision.action_id)
        if action is None:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=None,
                code=CONFIRMATION_ACTION_NOT_FOUND,
                message="Pending action was not found",
            )

        if action.status in (
            PendingActionStatus.EXECUTED,
            PendingActionStatus.FAILED,
            PendingActionStatus.REJECTED,
        ):
            return self._handle_terminal_action(decision, session, action)
        if action.status == PendingActionStatus.EXPIRED:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.EXPIRED,
                tool_name=action.tool_name,
                code=CONFIRMATION_ACTION_EXPIRED,
                message="Pending action has expired",
            )
        if action.status == PendingActionStatus.EXECUTING:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=TOOL_EXECUTION_STATE_UNKNOWN,
                message="Pending action execution state is unknown",
            )
        if action.status == PendingActionStatus.APPROVED and decision.decision == ConfirmationDecisionType.REJECT:
            return _conflict_result(decision, action)

        binding = self._validate_active_binding(decision, session, action)
        if isinstance(binding, ConfirmationResolutionResult):
            return binding

        expired = self._expire_if_needed(decision, binding.action)
        if expired is not None:
            return expired

        if decision.decision == ConfirmationDecisionType.REJECT:
            return self._reject(decision, binding)
        return self._approve(decision, binding)

    def _validate_active_binding(
        self,
        decision: ConfirmationDecision,
        session: AgentSession,
        action: PendingAction,
    ) -> _Binding | ConfirmationResolutionResult:
        """校验当前 Session/Action/Continuation/ToolCall 是否一致。"""

        if session.status != AgentSessionStatus.WAITING_CONFIRMATION:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=CONFIRMATION_SESSION_MISMATCH,
                message="Session is not waiting for confirmation",
            )
        if session.pending_action_id != decision.action_id:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=CONFIRMATION_SESSION_MISMATCH,
                message="Session pending action does not match decision",
            )
        if action.session_id != session.session_id:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=CONFIRMATION_SESSION_MISMATCH,
                message="Pending action belongs to a different session",
            )
        if action.action_id != session.pending_action_id:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=CONFIRMATION_SESSION_MISMATCH,
                message="Pending action id does not match session pointer",
            )
        continuation = session.continuation
        if continuation is None:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=CONFIRMATION_CONTINUATION_INVALID,
                message="Session continuation is missing",
            )
        tool_call_or_error = _current_tool_call(session, continuation)
        if isinstance(tool_call_or_error, AgentRunError):
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=tool_call_or_error.code,
                message=tool_call_or_error.message,
            )
        tool_call = tool_call_or_error
        if tool_call.id != action.tool_call_id:
            return _snapshot_error(decision, action, "Tool call id does not match action")
        if tool_call.name != action.tool_name:
            return _snapshot_error(decision, action, "Tool name does not match action")
        if calculate_arguments_hash(tool_call.arguments) != action.arguments_hash:
            return _snapshot_error(decision, action, "Tool call arguments changed")
        if calculate_arguments_hash(action.arguments) != action.arguments_hash:
            return _snapshot_error(decision, action, "Action arguments hash mismatch")

        definition = self.tool_registry.get(action.tool_name)
        if definition is None:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=CONFIRMATION_TOOL_NOT_FOUND,
                message="Tool definition was not found",
            )
        if definition.permission != ToolPermission.CONFIRMATION_REQUIRED:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=CONFIRMATION_PERMISSION_CHANGED,
                message="Tool permission changed before confirmation was resolved",
            )
        return _Binding(
            session=session,
            action=action,
            continuation=continuation,
            tool_call=tool_call,
        )

    def _expire_if_needed(
        self,
        decision: ConfirmationDecision,
        action: PendingAction,
    ) -> ConfirmationResolutionResult | None:
        """如果用户确认已过期，则只把 PENDING Action 转为 EXPIRED。"""

        if self._now() < action.expires_at:
            return None
        if action.status == PendingActionStatus.PENDING:
            try:
                expired = transition_pending_action(
                    action,
                    PendingActionStatus.EXPIRED,
                    now=self._now(),
                )
                self.pending_action_store.save(expired, expected_version=action.version)
            except PendingActionStoreError:
                return _error_result(
                    decision=decision,
                    status=ConfirmationResolutionStatus.FAILED,
                    tool_name=action.tool_name,
                    code=CONFIRMATION_ACTION_SAVE_FAILED,
                    message="Expired pending action could not be saved",
                )
        return _error_result(
            decision=decision,
            status=ConfirmationResolutionStatus.EXPIRED,
            tool_name=action.tool_name,
            code=CONFIRMATION_ACTION_EXPIRED,
            message="Pending action has expired",
        )

    def _approve(
        self,
        decision: ConfirmationDecision,
        binding: _Binding,
    ) -> ConfirmationResolutionResult:
        """执行 PENDING/APPROVED Action 并保存结果。"""

        action = binding.action
        if action.status == PendingActionStatus.PENDING:
            approved = transition_pending_action(
                action,
                PendingActionStatus.APPROVED,
                now=self._now(),
            )
            saved = self._save_action_or_error(
                decision=decision,
                action=approved,
                expected_version=action.version,
            )
            if isinstance(saved, ConfirmationResolutionResult):
                return saved
            action = saved

        executing = transition_pending_action(
            action,
            PendingActionStatus.EXECUTING,
            now=self._now(),
        )
        saved_executing = self._save_action_or_error(
            decision=decision,
            action=executing,
            expected_version=action.version,
        )
        if isinstance(saved_executing, ConfirmationResolutionResult):
            return saved_executing

        try:
            tool_result = self.approved_action_executor.execute(saved_executing.action_id)
        except ApprovedActionExecutionError as exc:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=saved_executing.tool_name,
                code=exc.code,
                message=exc.message,
            )

        final_status = (
            PendingActionStatus.EXECUTED
            if tool_result.success
            else PendingActionStatus.FAILED
        )
        final_action = transition_pending_action(
            saved_executing,
            final_status,
            now=self._now(),
            result_content=tool_result.content,
            result_error_code=tool_result.error_code,
        )
        saved_final = self._save_action_or_error(
            decision=decision,
            action=final_action,
            expected_version=saved_executing.version,
            error_code=TOOL_EXECUTION_STATE_UNKNOWN,
            error_message="Tool executed but final action result could not be saved",
        )
        if isinstance(saved_final, ConfirmationResolutionResult):
            return saved_final
        return self._finish_session(
            decision=decision,
            session=binding.session,
            action=saved_final,
            tool_result=tool_result,
            status=ConfirmationResolutionStatus.RESOLVED,
        )

    def _reject(
        self,
        decision: ConfirmationDecision,
        binding: _Binding,
    ) -> ConfirmationResolutionResult:
        """拒绝当前 Tool Call 并生成结构化 role=tool 结果。"""

        tool_result = _rejection_tool_result(binding.action)
        rejected = transition_pending_action(
            binding.action,
            PendingActionStatus.REJECTED,
            now=self._now(),
            result_content=tool_result.content,
            result_error_code=tool_result.error_code,
            decision_reason=decision.reason,
        )
        saved = self._save_action_or_error(
            decision=decision,
            action=rejected,
            expected_version=binding.action.version,
        )
        if isinstance(saved, ConfirmationResolutionResult):
            return saved
        return self._finish_session(
            decision=decision,
            session=binding.session,
            action=saved,
            tool_result=tool_result,
            status=ConfirmationResolutionStatus.REJECTED,
        )

    def _handle_terminal_action(
        self,
        decision: ConfirmationDecision,
        session: AgentSession,
        action: PendingAction,
    ) -> ConfirmationResolutionResult:
        """处理已经完成的 Action，支持安全幂等重放。"""

        if action.session_id != session.session_id:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=CONFIRMATION_SESSION_MISMATCH,
                message="Pending action belongs to a different session",
            )
        if action.status == PendingActionStatus.REJECTED:
            if decision.decision != ConfirmationDecisionType.REJECT:
                return _conflict_result(decision, action)
            tool_result = _tool_result_from_action(action)
            return self._finish_session(
                decision=decision,
                session=session,
                action=action,
                tool_result=tool_result,
                status=ConfirmationResolutionStatus.REJECTED,
            )
        if decision.decision != ConfirmationDecisionType.APPROVE:
            return _conflict_result(decision, action)
        tool_result = _tool_result_from_action(action)
        return self._finish_session(
            decision=decision,
            session=session,
            action=action,
            tool_result=tool_result,
            status=ConfirmationResolutionStatus.RESOLVED,
        )

    def _finish_session(
        self,
        *,
        decision: ConfirmationDecision,
        session: AgentSession,
        action: PendingAction,
        tool_result: ToolExecutionResult,
        status: ConfirmationResolutionStatus,
    ) -> ConfirmationResolutionResult:
        """追加或重放 role=tool 结果，并把 Session 切回 ACTIVE。"""

        continuation = session.continuation
        if continuation is None:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=CONFIRMATION_CONTINUATION_INVALID,
                message="Session continuation is missing",
            )

        existing = _find_tool_message(session, action.tool_call_id)
        should_save = False
        if existing is not None:
            if existing.content != tool_result.content:
                return _error_result(
                    decision=decision,
                    status=ConfirmationResolutionStatus.FAILED,
                    tool_name=action.tool_name,
                    code=CONFIRMATION_TOOL_RESULT_MISMATCH,
                    message="Existing tool message does not match stored action result",
                )
        else:
            session.messages.append(_tool_result_message(tool_result))
            should_save = True

        next_tool_call_index = action.tool_call_index + 1
        tool_calls_used = continuation.tool_calls_used + (
            0 if continuation.next_tool_call_index > action.tool_call_index else 1
        )
        updated_continuation = replace(
            continuation,
            next_tool_call_index=max(
                continuation.next_tool_call_index,
                next_tool_call_index,
            ),
            tool_calls_used=tool_calls_used,
        )
        if (
            session.status != AgentSessionStatus.ACTIVE
            or session.pending_action_id is not None
            or session.continuation != updated_continuation
        ):
            session.status = AgentSessionStatus.ACTIVE
            session.pending_action_id = None
            session.continuation = updated_continuation
            should_save = True

        if should_save:
            try:
                session = self.session_store.save(session, expected_version=session.version)
            except SessionStoreError:
                return _error_result(
                    decision=decision,
                    status=ConfirmationResolutionStatus.FAILED,
                    tool_name=action.tool_name,
                    code=CONFIRMATION_SESSION_SAVE_FAILED,
                    message="Session could not be saved after confirmation",
                )

        continuation = session.continuation
        return ConfirmationResolutionResult(
            status=status,
            session_id=session.session_id,
            action_id=action.action_id,
            tool_name=action.tool_name,
            decision=decision.decision,
            tool_succeeded=tool_result.success,
            model_turns_used=continuation.model_turns_used if continuation else None,
            tool_calls_used=continuation.tool_calls_used if continuation else None,
            next_tool_call_index=(
                continuation.next_tool_call_index if continuation else None
            ),
            remaining_runtime_seconds=(
                continuation.remaining_runtime_seconds if continuation else None
            ),
        )

    def _save_action_or_error(
        self,
        *,
        decision: ConfirmationDecision,
        action: PendingAction,
        expected_version: int,
        error_code: str = CONFIRMATION_ACTION_SAVE_FAILED,
        error_message: str = "Pending action could not be saved",
    ) -> PendingAction | ConfirmationResolutionResult:
        """按 CAS 保存 Action，失败时返回安全错误。"""

        try:
            return self.pending_action_store.save(action, expected_version=expected_version)
        except PendingActionStoreError:
            return _error_result(
                decision=decision,
                status=ConfirmationResolutionStatus.FAILED,
                tool_name=action.tool_name,
                code=error_code,
                message=error_message,
            )

    def _now(self) -> datetime:
        """返回 UTC aware 当前时间。"""

        value = self.now_provider() if self.now_provider else datetime.now(UTC)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("now_provider must return timezone-aware datetime")
        return value.astimezone(UTC)


def _current_tool_call(
    session: AgentSession,
    continuation: AgentContinuation,
) -> ModelToolCall | AgentRunError:
    """按 continuation 定位当前等待确认的 Tool Call。"""

    if continuation.assistant_message_index >= len(session.messages):
        return AgentRunError(
            code=CONFIRMATION_CONTINUATION_INVALID,
            message="assistant_message_index is out of range",
        )
    assistant_message = session.messages[continuation.assistant_message_index]
    if assistant_message.role != "assistant":
        return AgentRunError(
            code=CONFIRMATION_CONTINUATION_INVALID,
            message="continuation does not point to an assistant message",
        )
    tool_calls = tuple(assistant_message.tool_calls or ())
    if not tool_calls:
        return AgentRunError(
            code=CONFIRMATION_CONTINUATION_INVALID,
            message="assistant message has no tool calls",
        )
    if continuation.next_tool_call_index >= len(tool_calls):
        return AgentRunError(
            code=CONFIRMATION_CONTINUATION_INVALID,
            message="next_tool_call_index is out of range",
        )
    return tool_calls[continuation.next_tool_call_index]


def _find_tool_message(
    session: AgentSession,
    tool_call_id: str,
) -> ModelMessage | None:
    """查找已保存的 role=tool 消息，用于幂等去重。"""

    for message in session.messages:
        if message.role == "tool" and message.tool_call_id == tool_call_id:
            return message
    return None


def _tool_result_message(result: ToolExecutionResult) -> ModelMessage:
    """把 ToolExecutionResult 转换为 role=tool 消息。"""

    return ModelMessage(
        role="tool",
        content=result.content,
        name=result.tool_name,
        tool_call_id=result.tool_call_id,
    )


def _tool_result_from_action(action: PendingAction) -> ToolExecutionResult:
    """从 PendingAction 保存的结果重建 ToolExecutionResult。"""

    if action.result_content is None:
        raise ValueError("terminal action has no result_content")
    return ToolExecutionResult(
        tool_call_id=action.tool_call_id,
        tool_name=action.tool_name,
        success=action.result_error_code is None,
        content=action.result_content,
        error_code=action.result_error_code,
    )


def _rejection_tool_result(action: PendingAction) -> ToolExecutionResult:
    """构造标准拒绝 Tool Result，不回显完整 reason 或 arguments。"""

    return ToolExecutionResult(
        tool_call_id=action.tool_call_id,
        tool_name=action.tool_name,
        success=False,
        content=error_content(
            TOOL_REJECTED_BY_USER,
            "The user rejected this tool action.",
        ),
        error_code=TOOL_REJECTED_BY_USER,
    )


def _snapshot_error(
    decision: ConfirmationDecision,
    action: PendingAction,
    message: str,
) -> ConfirmationResolutionResult:
    return _error_result(
        decision=decision,
        status=ConfirmationResolutionStatus.FAILED,
        tool_name=action.tool_name,
        code=CONFIRMATION_SNAPSHOT_MISMATCH,
        message=message,
    )


def _conflict_result(
    decision: ConfirmationDecision,
    action: PendingAction,
) -> ConfirmationResolutionResult:
    return _error_result(
        decision=decision,
        status=ConfirmationResolutionStatus.CONFLICT,
        tool_name=action.tool_name,
        code=CONFIRMATION_DECISION_CONFLICT,
        message="Confirmation decision conflicts with existing action state",
    )


def _error_result(
    *,
    decision: ConfirmationDecision,
    status: ConfirmationResolutionStatus,
    tool_name: str | None,
    code: str,
    message: str,
) -> ConfirmationResolutionResult:
    return ConfirmationResolutionResult(
        status=status,
        session_id=decision.session_id,
        action_id=decision.action_id,
        tool_name=tool_name,
        decision=decision.decision,
        error=AgentRunError(code=code, message=message),
    )
