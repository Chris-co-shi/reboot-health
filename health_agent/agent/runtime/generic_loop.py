"""通用模型回合循环。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

from agent.models import ModelMessage, ModelProvider, ProviderResponseError
from agent.models.base import freeze_mapping
from agent.runtime.approval_policy import ApprovalPolicy, ToolDisposition
from agent.runtime.continuation import AgentContinuation
from agent.runtime.context import build_runtime_environment
from agent.runtime.pending_action import PendingAction, PendingActionStatus
from agent.runtime.pending_action_store import (
    InMemoryPendingActionStore,
    PendingActionStoreError,
)
from agent.runtime.result import AgentRunError, AgentRunResult, PendingActionSummary
from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    InMemorySessionStore,
    SessionStoreError,
    SessionVersionConflictError,
)
from agent.runtime.trace import TraceRecorder
from agent.tools.contract import ToolExecutionResult, error_content
from agent.tools.executor import PreparedToolCall, ToolExecutor
from agent.tools.registry import ToolRegistry

GENERIC_TRIGGER_TYPE = "GENERIC_AGENT"
GENERIC_STATUS_COMPLETED = "completed"
GENERIC_STATUS_MODEL_ERROR = "model_error"
GENERIC_STATUS_INVALID_RESPONSE = "invalid_response"
GENERIC_STATUS_LIMIT_REACHED = "limit_reached"
GENERIC_STATUS_WAITING_CONFIRMATION = "waiting_confirmation"
GENERIC_STATUS_FAILED = "failed"
ERROR_MODEL_ERROR = "MODEL_ERROR"
ERROR_INVALID_RESPONSE = "INVALID_RESPONSE"
ERROR_MAX_MODEL_TURNS_REACHED = "MAX_MODEL_TURNS_REACHED"
ERROR_MAX_TOOL_CALLS_REACHED = "MAX_TOOL_CALLS_REACHED"
ERROR_TIMEOUT_REACHED = "TIMEOUT_REACHED"
ERROR_SESSION_WAITING_CONFIRMATION = "SESSION_WAITING_CONFIRMATION"
ERROR_SESSION_STATE_CONFLICT = "SESSION_STATE_CONFLICT"
ERROR_SESSION_VERSION_CONFLICT = "SESSION_VERSION_CONFLICT"
ERROR_PENDING_ACTION_CREATE_FAILED = "PENDING_ACTION_CREATE_FAILED"
TOOL_POLICY_DENIED = "tool_policy_denied"
DEFAULT_CONFIRMATION_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class AgentRequest:
    """通用 Agent 输入合同。"""

    user_text: str
    session_id: str | None = None
    locale: str = "zh-CN"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        user_text = str(self.user_text or "").strip()
        if not user_text:
            raise ValueError("AgentRequest user_text must not be empty")
        object.__setattr__(self, "user_text", user_text)

        locale = str(self.locale or "").strip()
        if not locale:
            raise ValueError("AgentRequest locale must not be empty")
        object.__setattr__(self, "locale", locale)

        session_id = str(self.session_id).strip() if self.session_id is not None else None
        object.__setattr__(self, "session_id", session_id or None)

        if not isinstance(self.metadata, Mapping):
            raise ValueError("AgentRequest metadata must be a mapping")
        object.__setattr__(self, "metadata", freeze_mapping(self.metadata))


@dataclass(frozen=True)
class GenericLoopLimits:
    """通用 Agent 循环限制。"""

    max_model_turns: int = 6
    max_tool_calls: int = 8
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.max_model_turns <= 0:
            raise ValueError("max_model_turns must be positive")
        if self.max_tool_calls < 0:
            raise ValueError("max_tool_calls must be non-negative")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


class GenericAgentLoop:
    """不经过 trigger 的通用模型回合循环。"""

    def __init__(
        self,
        provider: ModelProvider,
        limits: GenericLoopLimits | None = None,
        session_store: InMemorySessionStore | None = None,
        trace_recorder: TraceRecorder | None = None,
        now_provider: Callable[[], datetime] | None = None,
        system_prompt_path: Path | None = None,
        tool_registry: ToolRegistry | None = None,
        tool_executor: ToolExecutor | None = None,
        approval_policy: ApprovalPolicy | None = None,
        pending_action_store: InMemoryPendingActionStore | None = None,
        confirmation_ttl_seconds: float = DEFAULT_CONFIRMATION_TTL_SECONDS,
        action_id_factory: Callable[[], str] | None = None,
        monotonic_provider: Callable[[], float] | None = None,
    ) -> None:
        if confirmation_ttl_seconds <= 0:
            raise ValueError("confirmation_ttl_seconds must be positive")
        self.provider = provider
        self.limits = limits or GenericLoopLimits()
        self.session_store = session_store or InMemorySessionStore()
        self.trace_recorder = trace_recorder or TraceRecorder()
        self.now_provider = now_provider
        self.system_prompt_path = system_prompt_path or _default_system_prompt_path()
        self.tool_registry = self._resolve_tool_registry(tool_registry, tool_executor)
        self.tool_executor = self._resolve_tool_executor(self.tool_registry, tool_executor)
        self.approval_policy = approval_policy or ApprovalPolicy()
        self.pending_action_store = pending_action_store or InMemoryPendingActionStore()
        self.confirmation_ttl_seconds = float(confirmation_ttl_seconds)
        self.action_id_factory = action_id_factory or _default_action_id
        self.monotonic_provider = monotonic_provider or time.monotonic

    def run(self, request: AgentRequest) -> AgentRunResult:
        """执行一次有限模型回合循环。"""
        started = self.monotonic_provider()
        deadline = started + self.limits.timeout_seconds
        wall_clock_started = self._wall_clock_now()
        started_at = _require_aware_utc(wall_clock_started)
        deadline_at = started_at + timedelta(seconds=self.limits.timeout_seconds)
        session = self.session_store.get_or_create(
            session_id=request.session_id,
            locale=request.locale,
        )
        provider_name = str(getattr(self.provider, "provider_name", "unknown"))
        trace = self.trace_recorder.start(
            session_id=session.session_id,
            trigger_type=GENERIC_TRIGGER_TYPE,
            provider=provider_name,
        )
        self.trace_recorder.record_step(
            trace,
            "run_started",
            {"provider": provider_name, "modelTurns": 0, "toolCallCount": 0},
        )

        waiting_result = self._existing_waiting_confirmation_result(
            trace=trace,
            session=session,
            started=started,
        )
        if waiting_result is not None:
            return waiting_result

        start_error = self._validate_startable_session(
            trace=trace,
            session=session,
            started=started,
        )
        if start_error is not None:
            return start_error

        runtime_environment = build_runtime_environment(
            now=wall_clock_started if self.now_provider else None,
            locale=request.locale,
        )
        try:
            session = self._start_session_turn(
                session=session,
                request=request,
                runtime_environment_payload=runtime_environment.to_provider_payload(),
            )
        except SessionStoreError as exc:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=tuple(session.messages),
                error_code=_session_error_code(exc),
                message="Session could not be saved before model execution",
            )
        self.trace_recorder.record_step(
            trace,
            "context_built",
            {"topLevelKeys": ["runtimeEnvironment"]},
        )

        model_turns = 0
        tool_calls = 0
        tool_definitions = self.tool_registry.to_model_definitions()

        while model_turns < self.limits.max_model_turns:
            if self._deadline_reached(deadline):
                return self._limit_reached(
                    trace=trace,
                    session_id=session.session_id,
                    started=started,
                    model_turns=model_turns,
                    tool_calls=tool_calls,
                    messages=tuple(session.messages),
                    error_code=ERROR_TIMEOUT_REACHED,
                    message="Agent run timed out before the next model turn",
                    limit_type="timeout",
                )

            model_turns += 1
            self.trace_recorder.record_step(
                trace,
                "model_turn_started",
                {
                    "modelTurns": model_turns,
                    "toolCallCount": tool_calls,
                    "provider": provider_name,
                },
            )
            try:
                response = self.provider.complete_turn(
                    messages=tuple(session.messages),
                    tools=tool_definitions,
                )
            except ProviderResponseError as exc:
                trace.warnings.append(exc.safe_summary)
                session = self._best_effort_status(session, AgentSessionStatus.FAILED)
                self.trace_recorder.finish(trace, GENERIC_STATUS_MODEL_ERROR)
                self.trace_recorder.record_step(
                    trace,
                    "run_finished",
                    {
                        "finalStatus": GENERIC_STATUS_MODEL_ERROR,
                        "modelTurns": model_turns,
                        "toolCallCount": tool_calls,
                        "errorCode": ERROR_MODEL_ERROR,
                        "elapsedMs": self._elapsed_ms(started),
                    },
                )
                return self._result(
                    trace=trace,
                    session_id=session.session_id,
                    status=GENERIC_STATUS_MODEL_ERROR,
                    model_turns=model_turns,
                    tool_calls=tool_calls,
                    messages=tuple(session.messages),
                    error=AgentRunError(code=ERROR_MODEL_ERROR, message=exc.safe_summary),
                )

            assistant_message_index = len(session.messages)
            assistant_message = (
                ModelMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )
            try:
                session = self._append_and_save(session, assistant_message)
            except SessionStoreError as exc:
                return self._session_error_result(
                    trace=trace,
                    session_id=session.session_id,
                    started=started,
                    model_turns=model_turns,
                    tool_calls=tool_calls,
                    finish_reason=response.finish_reason,
                    messages=tuple(session.messages),
                    error_code=_session_error_code(exc),
                    message="Session could not save assistant message",
                )
            self.trace_recorder.record_step(
                trace,
                "model_turn_completed",
                {
                    "modelTurns": model_turns,
                    "toolCallCount": tool_calls,
                    "finishReason": response.finish_reason,
                    "contentChars": len(response.content or ""),
                },
            )

            if self._deadline_reached(deadline):
                return self._limit_reached(
                    trace=trace,
                    session_id=session.session_id,
                    started=started,
                    model_turns=model_turns,
                    tool_calls=tool_calls,
                    finish_reason=response.finish_reason,
                    messages=tuple(session.messages),
                    error_code=ERROR_TIMEOUT_REACHED,
                    message="Agent run timed out after the model turn",
                    limit_type="timeout",
                )

            if response.tool_calls:
                batch_size = len(response.tool_calls)
                if model_turns >= self.limits.max_model_turns:
                    return self._limit_reached(
                        trace=trace,
                        session_id=session.session_id,
                        started=started,
                        model_turns=model_turns,
                        tool_calls=tool_calls,
                        finish_reason=response.finish_reason,
                        messages=tuple(session.messages),
                        error_code=ERROR_MAX_MODEL_TURNS_REACHED,
                        message="Maximum model turns reached before tool results could be returned",
                        limit_type="max_model_turns",
                    )
                if tool_calls + batch_size > self.limits.max_tool_calls:
                    return self._limit_reached(
                        trace=trace,
                        session_id=session.session_id,
                        started=started,
                        model_turns=model_turns,
                        tool_calls=tool_calls,
                        finish_reason=response.finish_reason,
                        messages=tuple(session.messages),
                        error_code=ERROR_MAX_TOOL_CALLS_REACHED,
                        message="Maximum tool calls reached before executing the current batch",
                        limit_type="max_tool_calls",
                    )
                if self._deadline_reached(deadline):
                    return self._limit_reached(
                        trace=trace,
                        session_id=session.session_id,
                        started=started,
                        model_turns=model_turns,
                        tool_calls=tool_calls,
                        finish_reason=response.finish_reason,
                        messages=tuple(session.messages),
                        error_code=ERROR_TIMEOUT_REACHED,
                        message="Agent run timed out before executing tools",
                        limit_type="timeout",
                    )

                self.trace_recorder.record_step(
                    trace,
                    "tool_batch_started",
                    {
                        "modelTurns": model_turns,
                        "toolCallCount": tool_calls,
                    },
                )
                for tool_call_index, tool_call in enumerate(response.tool_calls):
                    if self._deadline_reached(deadline):
                        return self._limit_reached(
                            trace=trace,
                            session_id=session.session_id,
                            started=started,
                            model_turns=model_turns,
                            tool_calls=tool_calls,
                            finish_reason=response.finish_reason,
                            messages=tuple(session.messages),
                            error_code=ERROR_TIMEOUT_REACHED,
                            message="Agent run timed out before executing a tool",
                            limit_type="timeout",
                        )

                    self.trace_recorder.record_step(
                        trace,
                        "tool_call_started",
                        {
                            "modelTurns": model_turns,
                            "toolCallCount": tool_calls,
                            "toolName": tool_call.name,
                        },
                    )

                    preflight = self.tool_executor.preflight(tool_call)
                    if preflight.error_result is not None:
                        result = preflight.error_result
                    else:
                        prepared_call = preflight.prepared_call
                        if prepared_call is None:
                            raise RuntimeError("Tool preflight returned no prepared call")
                        decision = self.approval_policy.evaluate(prepared_call.definition)
                        if decision.disposition == ToolDisposition.REQUIRE_CONFIRMATION:
                            return self._pause_for_confirmation(
                                trace=trace,
                                session=session,
                                prepared_call=prepared_call,
                                assistant_message_index=assistant_message_index,
                                tool_call_index=tool_call_index,
                                model_turns=model_turns,
                                tool_calls=tool_calls,
                                started=started,
                                started_at=started_at,
                                deadline_at=deadline_at,
                            )
                        if decision.disposition == ToolDisposition.EXECUTE_NOW:
                            result = self.tool_executor.execute_prepared(prepared_call)
                        else:
                            result = _policy_denied_result(
                                tool_call_id=prepared_call.tool_call_id,
                                tool_name=prepared_call.tool_name,
                                message=decision.message,
                            )

                    tool_calls += 1
                    try:
                        session = self._append_and_save(session, _tool_result_message(result))
                    except SessionStoreError as exc:
                        return self._session_error_result(
                            trace=trace,
                            session_id=session.session_id,
                            started=started,
                            model_turns=model_turns,
                            tool_calls=tool_calls,
                            finish_reason=response.finish_reason,
                            messages=tuple(session.messages),
                            error_code=_session_error_code(exc),
                            message="Session could not save tool result",
                        )

                    self._record_tool_result(
                        trace=trace,
                        result=result,
                        model_turns=model_turns,
                        tool_calls=tool_calls,
                    )

                    if self._deadline_reached(deadline):
                        return self._limit_reached(
                            trace=trace,
                            session_id=session.session_id,
                            started=started,
                            model_turns=model_turns,
                            tool_calls=tool_calls,
                            finish_reason=response.finish_reason,
                            messages=tuple(session.messages),
                            error_code=ERROR_TIMEOUT_REACHED,
                            message="Agent run timed out after executing a tool",
                            limit_type="timeout",
                        )

                self.trace_recorder.record_step(
                    trace,
                    "tool_batch_completed",
                    {
                        "modelTurns": model_turns,
                        "toolCallCount": tool_calls,
                    },
                )
                continue

            final_text = str(response.content or "").strip()
            if not final_text:
                session = self._best_effort_status(session, AgentSessionStatus.FAILED)
                self.trace_recorder.finish(trace, GENERIC_STATUS_INVALID_RESPONSE)
                self.trace_recorder.record_step(
                    trace,
                    "run_finished",
                    {
                        "finalStatus": GENERIC_STATUS_INVALID_RESPONSE,
                        "modelTurns": model_turns,
                        "toolCallCount": tool_calls,
                        "errorCode": ERROR_INVALID_RESPONSE,
                        "elapsedMs": self._elapsed_ms(started),
                    },
                )
                return self._result(
                    trace=trace,
                    session_id=session.session_id,
                    status=GENERIC_STATUS_INVALID_RESPONSE,
                    model_turns=model_turns,
                    tool_calls=tool_calls,
                    finish_reason=response.finish_reason,
                    messages=tuple(session.messages),
                    error=AgentRunError(
                        code=ERROR_INVALID_RESPONSE,
                        message="Model response content is empty",
                    ),
                )

            session = self._best_effort_status(session, AgentSessionStatus.COMPLETED)
            self.trace_recorder.finish(trace, GENERIC_STATUS_COMPLETED)
            self.trace_recorder.record_step(
                trace,
                "run_finished",
                {
                    "finalStatus": GENERIC_STATUS_COMPLETED,
                    "modelTurns": model_turns,
                    "toolCallCount": tool_calls,
                    "finishReason": response.finish_reason,
                    "elapsedMs": self._elapsed_ms(started),
                },
            )
            return self._result(
                trace=trace,
                session_id=session.session_id,
                status=GENERIC_STATUS_COMPLETED,
                model_turns=model_turns,
                tool_calls=tool_calls,
                finish_reason=response.finish_reason,
                messages=tuple(session.messages),
                final_text=final_text,
                output={"finalText": final_text},
            )

        return self._limit_reached(
            trace=trace,
            session_id=session.session_id,
            started=started,
            model_turns=model_turns,
            tool_calls=tool_calls,
            messages=tuple(session.messages),
            error_code=ERROR_MAX_MODEL_TURNS_REACHED,
            message="Maximum model turns reached",
            limit_type="max_model_turns",
        )

    def _start_session_turn(
        self,
        session: AgentSession,
        request: AgentRequest,
        runtime_environment_payload: Mapping[str, str],
    ) -> AgentSession:
        """把新的用户回合写入 Session，并用 CAS 保存。

        Session.messages 是后续 Pause/Resume 的权威消息历史；因此 system/user
        消息也必须在调用模型前进入 SessionStore，而不是只存在于局部变量。
        """

        session.status = AgentSessionStatus.ACTIVE
        session.pending_action_id = None
        session.continuation = None
        session.locale = request.locale
        if not session.messages:
            session.messages.append(self._system_message(runtime_environment_payload))
        session.messages.append(ModelMessage(role="user", content=request.user_text))
        return self.session_store.save(session, expected_version=session.version)

    def _system_message(
        self,
        runtime_environment_payload: Mapping[str, str],
    ) -> ModelMessage:
        """构造模型可见 system message。"""

        prompt = self.system_prompt_path.read_text(encoding="utf-8").strip()
        runtime_context = json.dumps(
            {"runtimeEnvironment": dict(runtime_environment_payload)},
            ensure_ascii=False,
            sort_keys=True,
        )
        return ModelMessage(
            role="system",
            content=f"{prompt}\n\nRuntime Environment:\n{runtime_context}",
        )

    def _append_and_save(
        self,
        session: AgentSession,
        message: ModelMessage,
    ) -> AgentSession:
        """追加一条消息并按当前 version CAS 保存。"""

        session.messages.append(message)
        return self.session_store.save(session, expected_version=session.version)

    def _existing_waiting_confirmation_result(
        self,
        trace,
        session: AgentSession,
        started: float,
    ) -> AgentRunResult | None:
        """处理已处于 WAITING_CONFIRMATION 的 Session。

        等待确认期间新的 user_text 不能进入消息历史，也不能再次调用模型。若
        Session 与 PendingActionStore 不一致，直接 fail closed。
        """

        if session.status != AgentSessionStatus.WAITING_CONFIRMATION:
            return None
        if not session.pending_action_id:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_STATE_CONFLICT,
                message="Session is waiting confirmation without pending_action_id",
            )
        action = self.pending_action_store.get(session.pending_action_id)
        if (
            action is None
            or action.session_id != session.session_id
            or action.status != PendingActionStatus.PENDING
        ):
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_STATE_CONFLICT,
                message="Session pending action is not available",
            )
        self.trace_recorder.finish(trace, GENERIC_STATUS_WAITING_CONFIRMATION)
        self.trace_recorder.record_step(
            trace,
            "run_finished",
            {
                "finalStatus": GENERIC_STATUS_WAITING_CONFIRMATION,
                "modelTurns": 0,
                "toolCallCount": 0,
                "elapsedMs": self._elapsed_ms(started),
            },
        )
        return self._result(
            trace=trace,
            session_id=session.session_id,
            status=GENERIC_STATUS_WAITING_CONFIRMATION,
            model_turns=0,
            tool_calls=0,
            messages=tuple(session.messages),
            pending_action=_pending_action_summary(action),
        )

    def _validate_startable_session(
        self,
        trace,
        session: AgentSession,
        started: float,
    ) -> AgentRunResult | None:
        """确认当前 Session 可以进入新的模型回合。"""

        if session.status not in (
            AgentSessionStatus.ACTIVE,
            AgentSessionStatus.COMPLETED,
        ):
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_STATE_CONFLICT,
                message="Session status cannot start a new agent run",
            )
        if session.pending_action_id or session.continuation is not None:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_STATE_CONFLICT,
                message="Session has unresolved confirmation state",
            )
        return None

    def _pause_for_confirmation(
        self,
        trace,
        session: AgentSession,
        prepared_call: PreparedToolCall,
        assistant_message_index: int,
        tool_call_index: int,
        model_turns: int,
        tool_calls: int,
        started: float,
        started_at: datetime,
        deadline_at: datetime,
    ) -> AgentRunResult:
        """创建 PendingAction 并把 Session 切换到 WAITING_CONFIRMATION。

        Store 之间没有事务原子性，因此顺序是先创建 PendingAction，再 CAS 保存
        Session 指针。若 Session 保存失败，返回失败结果，并承认可能留下 orphan
        PendingAction；这比让 Session 指向不存在的 action 更安全。
        """

        created_at = self._utc_now()
        action = PendingAction(
            action_id=self.action_id_factory(),
            session_id=session.session_id,
            originating_run_id=trace.run_id,
            tool_call_id=prepared_call.tool_call_id,
            tool_name=prepared_call.tool_name,
            arguments=prepared_call.arguments,
            assistant_message_index=assistant_message_index,
            tool_call_index=tool_call_index,
            summary=f'Tool "{prepared_call.tool_name}" requires user confirmation.',
            created_at=created_at,
            updated_at=created_at,
            expires_at=created_at + timedelta(seconds=self.confirmation_ttl_seconds),
        )
        try:
            action = self.pending_action_store.create(action)
        except PendingActionStoreError:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                messages=tuple(session.messages),
                error_code=ERROR_PENDING_ACTION_CREATE_FAILED,
                message="Pending action could not be created",
            )

        session.status = AgentSessionStatus.WAITING_CONFIRMATION
        session.pending_action_id = action.action_id
        session.continuation = AgentContinuation(
            originating_run_id=trace.run_id,
            assistant_message_index=assistant_message_index,
            next_tool_call_index=tool_call_index,
            model_turns_used=model_turns,
            tool_calls_used=tool_calls,
            started_at=started_at,
            deadline_at=deadline_at,
        )
        try:
            session = self.session_store.save(session, expected_version=session.version)
        except SessionStoreError as exc:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                messages=tuple(session.messages),
                error_code=_session_error_code(exc),
                message="Session could not be saved for confirmation pause",
            )

        self.trace_recorder.record_step(
            trace,
            "tool_confirmation_required",
            {
                "modelTurns": model_turns,
                "toolCallCount": tool_calls,
                "toolName": action.tool_name,
                "errorCode": ERROR_SESSION_WAITING_CONFIRMATION,
            },
        )
        self.trace_recorder.finish(trace, GENERIC_STATUS_WAITING_CONFIRMATION)
        self.trace_recorder.record_step(
            trace,
            "run_finished",
            {
                "finalStatus": GENERIC_STATUS_WAITING_CONFIRMATION,
                "modelTurns": model_turns,
                "toolCallCount": tool_calls,
                "elapsedMs": self._elapsed_ms(started),
            },
        )
        return self._result(
            trace=trace,
            session_id=session.session_id,
            status=GENERIC_STATUS_WAITING_CONFIRMATION,
            model_turns=model_turns,
            tool_calls=tool_calls,
            messages=tuple(session.messages),
            pending_action=_pending_action_summary(action),
        )

    def _record_tool_result(
        self,
        trace,
        result: ToolExecutionResult,
        model_turns: int,
        tool_calls: int,
    ) -> None:
        """记录已产生 role=tool result 的工具调用摘要。"""

        self.trace_recorder.record_tool_call(
            trace,
            {
                "toolName": result.tool_name,
                "success": result.success,
                "errorCode": result.error_code,
            },
        )
        self.trace_recorder.record_step(
            trace,
            "tool_call_completed" if result.success else "tool_call_failed",
            {
                "modelTurns": model_turns,
                "toolCallCount": tool_calls,
                "toolName": result.tool_name,
                "success": result.success,
                "errorCode": result.error_code,
            },
        )

    def _session_error_result(
        self,
        trace,
        session_id: str,
        started: float,
        model_turns: int,
        tool_calls: int,
        messages: tuple[ModelMessage, ...],
        error_code: str,
        message: str,
        finish_reason: str | None = None,
    ) -> AgentRunResult:
        """构造会话一致性错误结果，统一 fail closed。"""

        self.trace_recorder.finish(trace, GENERIC_STATUS_FAILED)
        self.trace_recorder.record_step(
            trace,
            "run_finished",
            {
                "finalStatus": GENERIC_STATUS_FAILED,
                "modelTurns": model_turns,
                "toolCallCount": tool_calls,
                "errorCode": error_code,
                "elapsedMs": self._elapsed_ms(started),
            },
        )
        return self._result(
            trace=trace,
            session_id=session_id,
            status=GENERIC_STATUS_FAILED,
            model_turns=model_turns,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            messages=messages,
            error=AgentRunError(code=error_code, message=message),
        )

    def _best_effort_status(
        self,
        session: AgentSession,
        status: AgentSessionStatus,
    ) -> AgentSession:
        """尽力保存终态；失败时不覆盖原始运行结果。"""

        session.status = status
        if status != AgentSessionStatus.WAITING_CONFIRMATION:
            session.pending_action_id = None
            session.continuation = None
        try:
            return self.session_store.save(session, expected_version=session.version)
        except SessionStoreError:
            return session

    def _wall_clock_now(self) -> datetime:
        """返回本次运行的 wall-clock 时间，支持测试注入。"""

        return self.now_provider() if self.now_provider else datetime.now(UTC)

    def _utc_now(self) -> datetime:
        """返回 UTC aware 当前时间。"""

        return _require_aware_utc(self._wall_clock_now())

    def _result(
        self,
        trace,
        session_id: str,
        status: str,
        model_turns: int,
        messages: tuple[ModelMessage, ...],
        tool_calls: int = 0,
        finish_reason: str | None = None,
        final_text: str | None = None,
        output: Mapping[str, Any] | None = None,
        error: AgentRunError | None = None,
        pending_action: PendingActionSummary | None = None,
    ) -> AgentRunResult:
        return AgentRunResult(
            run_id=trace.run_id,
            session_id=session_id,
            status=status,
            selected_skill=None,
            final_outcome=status,
            output=output or {},
            trace=trace,
            warnings=tuple(trace.warnings),
            error=error,
            final_text=final_text,
            messages=messages,
            model_turns=model_turns,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            pending_action=pending_action,
        )

    def _limit_reached(
        self,
        trace,
        session_id: str,
        started: float,
        model_turns: int,
        tool_calls: int,
        messages: tuple[ModelMessage, ...],
        error_code: str,
        message: str,
        limit_type: str,
        finish_reason: str | None = None,
    ) -> AgentRunResult:
        self.trace_recorder.finish(trace, GENERIC_STATUS_LIMIT_REACHED)
        self.trace_recorder.record_step(
            trace,
            "limit_reached",
            {
                "modelTurns": model_turns,
                "toolCallCount": tool_calls,
                "errorCode": error_code,
                "limitType": limit_type,
                "elapsedMs": self._elapsed_ms(started),
            },
        )
        self.trace_recorder.record_step(
            trace,
            "run_finished",
            {
                "finalStatus": GENERIC_STATUS_LIMIT_REACHED,
                "modelTurns": model_turns,
                "toolCallCount": tool_calls,
                "errorCode": error_code,
                "elapsedMs": self._elapsed_ms(started),
            },
        )
        return self._result(
            trace=trace,
            session_id=session_id,
            status=GENERIC_STATUS_LIMIT_REACHED,
            model_turns=model_turns,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            messages=messages,
            error=AgentRunError(code=error_code, message=message),
        )

    def _deadline_reached(self, deadline: float) -> bool:
        return self.monotonic_provider() >= deadline

    def _elapsed_ms(self, started: float) -> int:
        return max(0, int((self.monotonic_provider() - started) * 1000))

    @staticmethod
    def _resolve_tool_registry(
        tool_registry: ToolRegistry | None,
        tool_executor: ToolExecutor | None,
    ) -> ToolRegistry:
        if tool_registry is not None:
            return tool_registry
        if tool_executor is not None:
            return tool_executor.registry
        return ToolRegistry()

    @staticmethod
    def _resolve_tool_executor(
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor | None,
    ) -> ToolExecutor:
        if tool_executor is None:
            return ToolExecutor(tool_registry)
        if tool_executor.registry is not tool_registry:
            raise ValueError("tool_executor must use the same ToolRegistry instance")
        return tool_executor


def _default_system_prompt_path() -> Path:
    """返回默认中文系统提示词路径。"""

    return Path(__file__).resolve().parents[2] / "prompts" / "agent_system.zh-CN.md"


def _default_action_id() -> str:
    """生成 PendingAction 的不透明本地标识。"""

    return f"pending-action-{uuid4().hex}"


def _require_aware_utc(value: datetime) -> datetime:
    """要求 datetime 带时区，并统一转为 UTC。

    Confirmation continuation 需要用绝对 UTC 时间计算剩余预算；这里拒绝 naive
    datetime，避免测试或调用方传入本地时间后产生隐式偏移。
    """

    if not isinstance(value, datetime):
        raise ValueError("datetime value must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime value must be timezone-aware")
    return value.astimezone(UTC)


def _tool_result_message(result: ToolExecutionResult) -> ModelMessage:
    """把 ToolExecutionResult 转换成模型协议需要的 role=tool 消息。"""

    return ModelMessage(
        role="tool",
        content=result.content,
        name=result.tool_name,
        tool_call_id=result.tool_call_id,
    )


def _policy_denied_result(
    tool_call_id: str,
    tool_name: str,
    message: str,
) -> ToolExecutionResult:
    """构造 ApprovalPolicy 拒绝后的结构化 Tool Result。

    DENY 仍然以 role=tool 错误返回模型，而不是抛异常中断循环；这样模型有机会
    在下一回合改正调用，同时 trace 不会暴露工具参数。
    """

    return ToolExecutionResult(
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        success=False,
        content=error_content(TOOL_POLICY_DENIED, message),
        error_code=TOOL_POLICY_DENIED,
    )


def _pending_action_summary(action: PendingAction) -> PendingActionSummary:
    """从 PendingAction 生成外部可返回的安全摘要。"""

    return PendingActionSummary(
        action_id=action.action_id,
        tool_name=action.tool_name,
        summary=action.summary,
        expires_at=action.expires_at,
    )


def _session_error_code(exc: SessionStoreError) -> str:
    """把 SessionStore 异常收敛为稳定错误码。"""

    if isinstance(exc, SessionVersionConflictError):
        return ERROR_SESSION_VERSION_CONFLICT
    return ERROR_SESSION_STATE_CONFLICT
