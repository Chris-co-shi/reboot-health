"""通用模型回合循环。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, replace
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
from agent.runtime.run_ownership import RunOwnership
from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    InMemorySessionStore,
    SessionRunFenceLostError,
    SessionRunLeaseExpiredError,
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
ERROR_SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
ERROR_SESSION_NOT_RESUMABLE = "SESSION_NOT_RESUMABLE"
ERROR_SESSION_STILL_WAITING_CONFIRMATION = "SESSION_STILL_WAITING_CONFIRMATION"
ERROR_SESSION_ALREADY_RUNNING = "SESSION_ALREADY_RUNNING"
ERROR_SESSION_CONTINUATION_INVALID = "SESSION_CONTINUATION_INVALID"
ERROR_SESSION_MESSAGE_HISTORY_INVALID = "SESSION_MESSAGE_HISTORY_INVALID"
ERROR_SESSION_FINALIZATION_PERSIST_FAILED = "SESSION_FINALIZATION_PERSIST_FAILED"
ERROR_SESSION_FINALIZATION_STATE_UNKNOWN = "SESSION_FINALIZATION_STATE_UNKNOWN"
ERROR_SESSION_OWNERSHIP_LOST = "SESSION_OWNERSHIP_LOST"
ERROR_SESSION_STALE_RUN_REQUIRES_RECOVERY = "SESSION_STALE_RUN_REQUIRES_RECOVERY"
ERROR_SESSION_RUN_LEASE_EXPIRED = "SESSION_RUN_LEASE_EXPIRED"
ERROR_SESSION_RUN_FENCE_LOST = "SESSION_RUN_FENCE_LOST"
ERROR_PENDING_ACTION_CREATE_FAILED = "PENDING_ACTION_CREATE_FAILED"
TOOL_POLICY_DENIED = "tool_policy_denied"
DEFAULT_CONFIRMATION_TTL_SECONDS = 15 * 60
DEFAULT_RUN_LEASE_SAFETY_MARGIN_SECONDS = 5.0
DEFAULT_RUN_LEASE_EXTRA_SECONDS = 60.0


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


@dataclass
class _DriveState:
    """一次 RUNNING 占用内的可变执行游标。

    该结构只在 `GenericAgentLoop` 内部流转，避免把 Fresh Run 和 Resume 分裂成
    两套状态机。模型回合、工具次数和 active deadline 都从这里延续。
    """

    session: AgentSession
    model_turns: int
    tool_calls: int
    started: float
    active_deadline: float
    started_at: datetime
    deadline_at: datetime
    current_assistant_message_index: int | None = None
    next_tool_call_index: int = 0
    current_originating_run_id: str | None = None
    finish_reason: str | None = None
    ownership: RunOwnership | None = None


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
        run_lease_ttl_seconds: float | None = None,
        run_lease_heartbeat_interval_seconds: float | None = None,
        lease_safety_margin_seconds: float = DEFAULT_RUN_LEASE_SAFETY_MARGIN_SECONDS,
    ) -> None:
        if confirmation_ttl_seconds <= 0:
            raise ValueError("confirmation_ttl_seconds must be positive")
        self.provider = provider
        self.limits = limits or GenericLoopLimits()
        self.lease_safety_margin_seconds = _positive_or_zero(
            lease_safety_margin_seconds,
            "lease_safety_margin_seconds",
        )
        self.run_lease_ttl_seconds = self._resolve_run_lease_ttl(run_lease_ttl_seconds)
        self.run_lease_heartbeat_interval_seconds = (
            self._resolve_run_lease_heartbeat_interval(
                run_lease_heartbeat_interval_seconds
            )
        )
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

    def _resolve_run_lease_ttl(self, configured: float | None) -> float:
        """解析并校验 RUNNING lease TTL。

        Lease 使用 wall clock，而 active runtime timeout 使用 monotonic clock；TTL
        必须覆盖整个主动执行预算加安全边距，避免正常运行在预算内失租。
        """

        if configured is None:
            value = (
                self.limits.timeout_seconds
                + self.lease_safety_margin_seconds
                + DEFAULT_RUN_LEASE_EXTRA_SECONDS
            )
        else:
            value = float(configured)
        if value <= 0:
            raise ValueError("run_lease_ttl_seconds must be positive")
        if value <= self.limits.timeout_seconds + self.lease_safety_margin_seconds:
            raise ValueError(
                "run_lease_ttl_seconds must be greater than timeout_seconds "
                "plus lease_safety_margin_seconds"
            )
        return value

    def _resolve_run_lease_heartbeat_interval(self, configured: float | None) -> float:
        """解析 heartbeat interval；本 Slice 不启动后台线程，只用于合同配置。"""

        value = (
            min(10.0, self.run_lease_ttl_seconds / 2.0)
            if configured is None
            else float(configured)
        )
        if value <= 0:
            raise ValueError("run_lease_heartbeat_interval_seconds must be positive")
        if value >= self.run_lease_ttl_seconds:
            raise ValueError(
                "run_lease_heartbeat_interval_seconds must be less than run_lease_ttl_seconds"
            )
        return value

    def run(self, request: AgentRequest) -> AgentRunResult:
        """执行一次有限模型回合循环。"""
        started = self.monotonic_provider()
        active_deadline = started + self.limits.timeout_seconds
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

        claimed_or_error = self._claim_session(
            trace=trace,
            session=session,
            started=started,
            model_turns=0,
            tool_calls=0,
        )
        if isinstance(claimed_or_error, AgentRunResult):
            return claimed_or_error
        session, ownership = claimed_or_error

        runtime_environment = build_runtime_environment(
            now=wall_clock_started if self.now_provider else None,
            locale=request.locale,
        )
        try:
            session = self._start_session_turn(
                session=session,
                request=request,
                runtime_environment_payload=runtime_environment.to_provider_payload(),
                ownership=ownership,
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
                session=session,
            )
        self.trace_recorder.record_step(
            trace,
            "context_built",
            {"topLevelKeys": ["runtimeEnvironment"]},
        )

        state = _DriveState(
            session=session,
            model_turns=0,
            tool_calls=0,
            started=started,
            active_deadline=active_deadline,
            started_at=started_at,
            deadline_at=deadline_at,
            current_originating_run_id=trace.run_id,
            ownership=ownership,
        )
        return self._drive_session(
            trace=trace,
            state=state,
            provider_name=provider_name,
            is_resume=False,
        )

    def resume(self, session_id: str) -> AgentRunResult:
        """从已确认完成的 AgentContinuation 恢复执行。

        Resume 只消费 Session 中已有的 assistant/tool 消息历史，不接受新的用户
        输入、Tool arguments 或确认决策。Approve/Reject 已由
        ConfirmationCoordinator 表达成 role=tool Result。
        """

        requested_session_id = str(session_id or "").strip()
        started = self.monotonic_provider()
        provider_name = str(getattr(self.provider, "provider_name", "unknown"))
        trace = self.trace_recorder.start(
            session_id=requested_session_id or "missing-session",
            trigger_type=GENERIC_TRIGGER_TYPE,
            provider=provider_name,
        )
        self.trace_recorder.record_step(
            trace,
            "resume_started",
            {"provider": provider_name, "modelTurns": 0, "toolCallCount": 0},
        )

        session = self.session_store.get(requested_session_id)
        if session is None:
            return self._session_error_result(
                trace=trace,
                session_id=requested_session_id or "missing-session",
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=(),
                error_code=ERROR_SESSION_NOT_FOUND,
                message="Session was not found for resume",
                release_session=False,
            )

        if session.status == AgentSessionStatus.RUNNING:
            error_code = (
                ERROR_SESSION_STALE_RUN_REQUIRES_RECOVERY
                if self._session_lease_expired(session, self._utc_now())
                else ERROR_SESSION_ALREADY_RUNNING
            )
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=tuple(session.messages),
                error_code=error_code,
                message=(
                    "Session has a stale run that requires recovery"
                    if error_code == ERROR_SESSION_STALE_RUN_REQUIRES_RECOVERY
                    else "Session is already running"
                ),
                release_session=False,
            )
        if session.status == AgentSessionStatus.WAITING_CONFIRMATION:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_STILL_WAITING_CONFIRMATION,
                message="Session is still waiting for confirmation",
                release_session=False,
            )
        if session.status != AgentSessionStatus.ACTIVE:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_NOT_RESUMABLE,
                message="Session status is not resumable",
                release_session=False,
            )
        if session.pending_action_id is not None:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_STILL_WAITING_CONFIRMATION,
                message="Session still references a pending action",
                release_session=False,
            )

        continuation_or_error = self._validate_resume_continuation(
            trace=trace,
            session=session,
            started=started,
        )
        if isinstance(continuation_or_error, AgentRunResult):
            return continuation_or_error
        continuation = continuation_or_error

        claimed_or_error = self._claim_session(
            trace=trace,
            session=session,
            started=started,
            model_turns=continuation.model_turns_used,
            tool_calls=continuation.tool_calls_used,
        )
        if isinstance(claimed_or_error, AgentRunResult):
            return claimed_or_error
        session, ownership = claimed_or_error

        state = _DriveState(
            session=session,
            model_turns=continuation.model_turns_used,
            tool_calls=continuation.tool_calls_used,
            started=started,
            active_deadline=started + continuation.remaining_runtime_seconds,
            started_at=continuation.started_at,
            deadline_at=continuation.deadline_at,
            current_assistant_message_index=continuation.assistant_message_index,
            next_tool_call_index=continuation.next_tool_call_index,
            current_originating_run_id=continuation.originating_run_id,
            ownership=ownership,
        )
        return self._drive_session(
            trace=trace,
            state=state,
            provider_name=provider_name,
            is_resume=True,
        )

    def _drive_session(
        self,
        *,
        trace,
        state: _DriveState,
        provider_name: str,
        is_resume: bool,
    ) -> AgentRunResult:
        """驱动 Session 从 RUNNING 到完成、再次暂停或失败。

        Fresh Run 和 Resume 共享这个循环，确保预算、超时、权限和消息顺序只有一
        套实现。`state.session` 必须已经被当前 `trace.run_id` 成功 claim。
        """

        tool_definitions = self.tool_registry.to_model_definitions()
        heartbeat_error = self._heartbeat_state_or_result(
            trace=trace,
            state=state,
            message="Session ownership heartbeat failed before drive loop",
        )
        if heartbeat_error is not None:
            return heartbeat_error

        while True:
            if state.current_assistant_message_index is not None:
                resumed = self._process_tool_calls(
                    trace=trace,
                    state=state,
                    is_resume=is_resume,
                )
                if isinstance(resumed, AgentRunResult):
                    return resumed

            if state.model_turns >= self.limits.max_model_turns:
                return self._limit_reached(
                    trace=trace,
                    session=state.session,
                    started=state.started,
                    model_turns=state.model_turns,
                    tool_calls=state.tool_calls,
                    messages=tuple(state.session.messages),
                    error_code=ERROR_MAX_MODEL_TURNS_REACHED,
                    message="Maximum model turns reached",
                    limit_type="max_model_turns",
                    finish_reason=state.finish_reason,
                )

            if self._deadline_reached(state.active_deadline):
                return self._limit_reached(
                    trace=trace,
                    session=state.session,
                    started=state.started,
                    model_turns=state.model_turns,
                    tool_calls=state.tool_calls,
                    messages=tuple(state.session.messages),
                    error_code=ERROR_TIMEOUT_REACHED,
                    message="Agent run timed out before the next model turn",
                    limit_type="timeout",
                    finish_reason=state.finish_reason,
                )

            state.model_turns += 1
            self.trace_recorder.record_step(
                trace,
                "model_turn_started",
                {
                    "modelTurns": state.model_turns,
                    "toolCallCount": state.tool_calls,
                    "provider": provider_name,
                },
            )
            heartbeat_error = self._heartbeat_state_or_result(
                trace=trace,
                state=state,
                message="Session ownership heartbeat failed before model call",
            )
            if heartbeat_error is not None:
                return heartbeat_error
            try:
                response = self.provider.complete_turn(
                    messages=tuple(state.session.messages),
                    tools=tool_definitions,
                )
            except ProviderResponseError as exc:
                trace.warnings.append(exc.safe_summary)
                finalized = self._finalize_owned_session(
                    trace=trace,
                    session=state.session,
                    ownership=_require_ownership(state.ownership),
                    target_status=AgentSessionStatus.FAILED,
                    started=state.started,
                    model_turns=state.model_turns,
                    tool_calls=state.tool_calls,
                    finish_reason=state.finish_reason,
                )
                if isinstance(finalized, AgentRunResult):
                    return finalized
                state.session = finalized
                self.trace_recorder.finish(trace, GENERIC_STATUS_MODEL_ERROR)
                self.trace_recorder.record_step(
                    trace,
                    "run_finished",
                    {
                        "finalStatus": GENERIC_STATUS_MODEL_ERROR,
                        "modelTurns": state.model_turns,
                        "toolCallCount": state.tool_calls,
                        "errorCode": ERROR_MODEL_ERROR,
                        "elapsedMs": self._elapsed_ms(state.started),
                    },
                )
                return self._result(
                    trace=trace,
                    session_id=state.session.session_id,
                    status=GENERIC_STATUS_MODEL_ERROR,
                    model_turns=state.model_turns,
                    tool_calls=state.tool_calls,
                    messages=tuple(state.session.messages),
                    error=AgentRunError(code=ERROR_MODEL_ERROR, message=exc.safe_summary),
                )

            heartbeat_error = self._heartbeat_state_or_result(
                trace=trace,
                state=state,
                message="Session ownership heartbeat failed after model call",
            )
            if heartbeat_error is not None:
                return heartbeat_error
            assistant_message_index = len(state.session.messages)
            assistant_message = (
                ModelMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )
            try:
                state.session = self._append_and_save(
                    state.session,
                    assistant_message,
                    state.ownership,
                )
            except SessionStoreError as exc:
                return self._session_error_result(
                    trace=trace,
                    session_id=state.session.session_id,
                    started=state.started,
                    model_turns=state.model_turns,
                    tool_calls=state.tool_calls,
                    finish_reason=response.finish_reason,
                    messages=tuple(state.session.messages),
                    error_code=_session_error_code(exc),
                    message="Session could not save assistant message",
                    session=state.session,
                )
            state.finish_reason = response.finish_reason
            self.trace_recorder.record_step(
                trace,
                "model_turn_completed",
                {
                    "modelTurns": state.model_turns,
                    "toolCallCount": state.tool_calls,
                    "finishReason": response.finish_reason,
                    "contentChars": len(response.content or ""),
                },
            )

            if self._deadline_reached(state.active_deadline):
                return self._limit_reached(
                    trace=trace,
                    session=state.session,
                    started=state.started,
                    model_turns=state.model_turns,
                    tool_calls=state.tool_calls,
                    finish_reason=response.finish_reason,
                    messages=tuple(state.session.messages),
                    error_code=ERROR_TIMEOUT_REACHED,
                    message="Agent run timed out after the model turn",
                    limit_type="timeout",
                )

            if response.tool_calls:
                if state.model_turns >= self.limits.max_model_turns:
                    return self._limit_reached(
                        trace=trace,
                        session=state.session,
                        started=state.started,
                        model_turns=state.model_turns,
                        tool_calls=state.tool_calls,
                        finish_reason=response.finish_reason,
                        messages=tuple(state.session.messages),
                        error_code=ERROR_MAX_MODEL_TURNS_REACHED,
                        message="Maximum model turns reached before tool results could be returned",
                        limit_type="max_model_turns",
                    )
                state.current_assistant_message_index = assistant_message_index
                state.next_tool_call_index = 0
                state.current_originating_run_id = trace.run_id
                continue

            final_text = str(response.content or "").strip()
            if not final_text:
                finalized = self._finalize_owned_session(
                    trace=trace,
                    session=state.session,
                    ownership=_require_ownership(state.ownership),
                    target_status=AgentSessionStatus.FAILED,
                    started=state.started,
                    model_turns=state.model_turns,
                    tool_calls=state.tool_calls,
                    finish_reason=response.finish_reason,
                )
                if isinstance(finalized, AgentRunResult):
                    return finalized
                state.session = finalized
                self.trace_recorder.finish(trace, GENERIC_STATUS_INVALID_RESPONSE)
                self.trace_recorder.record_step(
                    trace,
                    "run_finished",
                    {
                        "finalStatus": GENERIC_STATUS_INVALID_RESPONSE,
                        "modelTurns": state.model_turns,
                        "toolCallCount": state.tool_calls,
                        "errorCode": ERROR_INVALID_RESPONSE,
                        "elapsedMs": self._elapsed_ms(state.started),
                    },
                )
                return self._result(
                    trace=trace,
                    session_id=state.session.session_id,
                    status=GENERIC_STATUS_INVALID_RESPONSE,
                    model_turns=state.model_turns,
                    tool_calls=state.tool_calls,
                    finish_reason=response.finish_reason,
                    messages=tuple(state.session.messages),
                    error=AgentRunError(
                        code=ERROR_INVALID_RESPONSE,
                        message="Model response content is empty",
                    ),
                )

            finalized = self._finalize_owned_session(
                trace=trace,
                session=state.session,
                ownership=_require_ownership(state.ownership),
                target_status=AgentSessionStatus.COMPLETED,
                started=state.started,
                model_turns=state.model_turns,
                tool_calls=state.tool_calls,
                finish_reason=response.finish_reason,
            )
            if isinstance(finalized, AgentRunResult):
                return finalized
            state.session = finalized
            self.trace_recorder.finish(trace, GENERIC_STATUS_COMPLETED)
            self.trace_recorder.record_step(
                trace,
                "run_finished",
                {
                    "finalStatus": GENERIC_STATUS_COMPLETED,
                    "modelTurns": state.model_turns,
                    "toolCallCount": state.tool_calls,
                    "finishReason": response.finish_reason,
                    "elapsedMs": self._elapsed_ms(state.started),
                },
            )
            return self._result(
                trace=trace,
                session_id=state.session.session_id,
                status=GENERIC_STATUS_COMPLETED,
                model_turns=state.model_turns,
                tool_calls=state.tool_calls,
                finish_reason=response.finish_reason,
                messages=tuple(state.session.messages),
                final_text=final_text,
                output={"finalText": final_text},
            )

    def _start_session_turn(
        self,
        session: AgentSession,
        request: AgentRequest,
        runtime_environment_payload: Mapping[str, str],
        ownership: RunOwnership,
    ) -> AgentSession:
        """把新的用户回合写入 Session，并用 CAS 保存。

        Session.messages 是后续 Pause/Resume 的权威消息历史；因此 system/user
        消息也必须在调用模型前进入 SessionStore，而不是只存在于局部变量。
        """

        session.status = AgentSessionStatus.RUNNING
        session.pending_action_id = None
        session.continuation = None
        session.locale = request.locale
        if not session.messages:
            session.messages.append(self._system_message(runtime_environment_payload))
        session.messages.append(ModelMessage(role="user", content=request.user_text))
        return self._save_owned_session(session, ownership)

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
        ownership: RunOwnership | None,
    ) -> AgentSession:
        """追加一条消息并按当前 version CAS 保存。"""

        session.messages.append(message)
        return self._save_owned_session(session, _require_ownership(ownership))

    def _save_owned_session(
        self,
        session: AgentSession,
        ownership: RunOwnership,
    ) -> AgentSession:
        """在保存前重新校验 Store 中的 owner、generation 和 lease。

        该方法是当前 run 写入 Session 的统一 fence。它先读取磁盘/Store 当前状态，
        再使用 expected_version CAS 保存，避免旧 generation 或过期 owner 覆盖新
        owner。普通 get 不调用模型或工具，因此不违反锁内外部调用边界。
        """

        current = self._assert_current_owner(ownership)
        if self._session_lease_expired(current, self._utc_now()):
            raise SessionRunLeaseExpiredError("Session run lease expired")
        try:
            return self.session_store.save(session, expected_version=session.version)
        except SessionVersionConflictError:
            current = self._assert_current_owner(ownership)
            if self._session_lease_expired(current, self._utc_now()):
                raise SessionRunLeaseExpiredError("Session run lease expired")
            raise

    def _heartbeat_state_or_result(
        self,
        *,
        trace,
        state: _DriveState,
        message: str,
    ) -> AgentRunResult | None:
        """为当前 state 做一次 owner heartbeat；失败时转换为稳定运行错误。"""

        try:
            state.session = self._heartbeat_owned_session(
                _require_ownership(state.ownership)
            )
            return None
        except SessionRunLeaseExpiredError:
            return self._session_error_result(
                trace=trace,
                session_id=state.session.session_id,
                started=state.started,
                model_turns=state.model_turns,
                tool_calls=state.tool_calls,
                finish_reason=state.finish_reason,
                messages=tuple(state.session.messages),
                error_code=ERROR_SESSION_RUN_LEASE_EXPIRED,
                message=message,
                release_session=False,
            )
        except SessionRunFenceLostError:
            return self._session_error_result(
                trace=trace,
                session_id=state.session.session_id,
                started=state.started,
                model_turns=state.model_turns,
                tool_calls=state.tool_calls,
                finish_reason=state.finish_reason,
                messages=tuple(state.session.messages),
                error_code=ERROR_SESSION_RUN_FENCE_LOST,
                message=message,
                release_session=False,
            )
        except SessionStoreError as exc:
            return self._session_error_result(
                trace=trace,
                session_id=state.session.session_id,
                started=state.started,
                model_turns=state.model_turns,
                tool_calls=state.tool_calls,
                finish_reason=state.finish_reason,
                messages=tuple(state.session.messages),
                error_code=_session_error_code(exc),
                message=message,
                release_session=False,
            )

    def _heartbeat_owned_session(self, ownership: RunOwnership) -> AgentSession:
        """续租当前 owner；过期或 fence 变化时拒绝复活旧 owner。"""

        current = self._assert_current_owner(ownership)
        now = self._utc_now()
        if self._session_lease_expired(current, now):
            raise SessionRunLeaseExpiredError("Session run lease expired")
        refreshed = replace(
            current,
            active_run_last_heartbeat_at=now,
            active_run_lease_expires_at=now + timedelta(seconds=self.run_lease_ttl_seconds),
        )
        try:
            return self.session_store.save(refreshed, expected_version=current.version)
        except SessionVersionConflictError:
            self._assert_current_owner(ownership)
            raise

    def _assert_current_owner(self, ownership: RunOwnership) -> AgentSession:
        current = self.session_store.get(ownership.session_id)
        if (
            current is None
            or current.status != AgentSessionStatus.RUNNING
            or current.active_run_id != ownership.run_id
            or current.run_fence_generation != ownership.fence_generation
        ):
            raise SessionRunFenceLostError("Session run fence lost")
        return current

    def _session_lease_expired(self, session: AgentSession, now: datetime) -> bool:
        """判断 RUNNING lease 是否已过期；无 lease 元数据按 stale 处理。"""

        if session.active_run_lease_expires_at is None:
            return True
        return _require_aware_utc(now) >= session.active_run_lease_expires_at

    def _claim_session(
        self,
        *,
        trace,
        session: AgentSession,
        started: float,
        model_turns: int,
        tool_calls: int,
    ) -> tuple[AgentSession, RunOwnership] | AgentRunResult:
        """把 ACTIVE/COMPLETED Session 原子切换为 RUNNING。

        只有 CAS 成功后才允许调用模型或工具。CAS 失败时会重新读取当前 Session，
        如果已被其它 run 占用，则返回稳定的 `SESSION_ALREADY_RUNNING`。
        """

        now = self._utc_now()
        if session.status == AgentSessionStatus.RUNNING:
            error_code = (
                ERROR_SESSION_STALE_RUN_REQUIRES_RECOVERY
                if self._session_lease_expired(session, now)
                else ERROR_SESSION_ALREADY_RUNNING
            )
            message = (
                "Session has a stale run that requires recovery"
                if error_code == ERROR_SESSION_STALE_RUN_REQUIRES_RECOVERY
                else "Session is already running"
            )
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                messages=tuple(session.messages),
                error_code=error_code,
                message=message,
                release_session=False,
            )

        generation = session.run_fence_generation + 1
        session.status = AgentSessionStatus.RUNNING
        session.active_run_id = trace.run_id
        session.run_fence_generation = generation
        session.active_run_last_heartbeat_at = now
        session.active_run_lease_expires_at = now + timedelta(
            seconds=self.run_lease_ttl_seconds
        )
        ownership = RunOwnership(
            session_id=session.session_id,
            run_id=trace.run_id,
            fence_generation=generation,
        )
        try:
            saved = self.session_store.save(session, expected_version=session.version)
            return saved, ownership
        except SessionVersionConflictError:
            latest = self.session_store.get(session.session_id)
            if latest is not None and latest.status == AgentSessionStatus.RUNNING:
                latest_now = self._utc_now()
                error_code = (
                    ERROR_SESSION_STALE_RUN_REQUIRES_RECOVERY
                    if self._session_lease_expired(latest, latest_now)
                    else ERROR_SESSION_ALREADY_RUNNING
                )
                message = (
                    "Session has a stale run that requires recovery"
                    if error_code == ERROR_SESSION_STALE_RUN_REQUIRES_RECOVERY
                    else "Session is already running"
                )
                return self._session_error_result(
                    trace=trace,
                    session_id=session.session_id,
                    started=started,
                    model_turns=model_turns,
                    tool_calls=tool_calls,
                    messages=tuple(latest.messages),
                    error_code=error_code,
                    message=message,
                    release_session=False,
                )
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_VERSION_CONFLICT,
                message="Session could not be claimed because its version changed",
                release_session=False,
            )
        except SessionStoreError as exc:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                messages=tuple(session.messages),
                error_code=_session_error_code(exc),
                message="Session could not be claimed for execution",
                release_session=False,
            )

    def _validate_resume_continuation(
        self,
        *,
        trace,
        session: AgentSession,
        started: float,
    ) -> AgentContinuation | AgentRunResult:
        """校验 Resume 的 continuation 与消息历史是否一致。

        已处理的 Tool Call 必须已有且仅有一条 role=tool Result；cursor 当前及
        后续 Tool Call 不能已有结果。遇到矛盾直接 fail closed，不通过重新执行
        handler 来修复历史。
        """

        continuation = session.continuation
        if continuation is None:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_NOT_RESUMABLE,
                message="Session has no continuation to resume",
                release_session=False,
            )
        if not session.messages:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=continuation.model_turns_used,
                tool_calls=continuation.tool_calls_used,
                messages=(),
                error_code=ERROR_SESSION_MESSAGE_HISTORY_INVALID,
                message="Session message history is empty",
                session=session,
            )
        assistant_or_error = self._assistant_message_for_continuation(
            session=session,
            continuation=continuation,
            trace=trace,
            started=started,
        )
        if isinstance(assistant_or_error, AgentRunResult):
            return assistant_or_error
        assistant_message = assistant_or_error
        tool_calls = tuple(assistant_message.tool_calls or ())
        if continuation.next_tool_call_index > len(tool_calls):
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=continuation.model_turns_used,
                tool_calls=continuation.tool_calls_used,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_CONTINUATION_INVALID,
                message="next_tool_call_index is out of range",
                session=session,
            )

        tool_result_counts = _tool_result_counts(session.messages)
        for tool_call_index, tool_call in enumerate(tool_calls):
            result_count = tool_result_counts.get(tool_call.id, 0)
            if result_count > 1:
                return self._session_error_result(
                    trace=trace,
                    session_id=session.session_id,
                    started=started,
                    model_turns=continuation.model_turns_used,
                    tool_calls=continuation.tool_calls_used,
                    messages=tuple(session.messages),
                    error_code=ERROR_SESSION_MESSAGE_HISTORY_INVALID,
                    message="Tool result is duplicated in message history",
                    session=session,
                )
            if tool_call_index < continuation.next_tool_call_index and result_count != 1:
                return self._session_error_result(
                    trace=trace,
                    session_id=session.session_id,
                    started=started,
                    model_turns=continuation.model_turns_used,
                    tool_calls=continuation.tool_calls_used,
                    messages=tuple(session.messages),
                    error_code=ERROR_SESSION_MESSAGE_HISTORY_INVALID,
                    message="Processed tool call has no matching tool result",
                    session=session,
                )
            if tool_call_index >= continuation.next_tool_call_index and result_count:
                return self._session_error_result(
                    trace=trace,
                    session_id=session.session_id,
                    started=started,
                    model_turns=continuation.model_turns_used,
                    tool_calls=continuation.tool_calls_used,
                    messages=tuple(session.messages),
                    error_code=ERROR_SESSION_MESSAGE_HISTORY_INVALID,
                    message="Unprocessed tool call already has a tool result",
                    session=session,
                )
        return continuation

    def _assistant_message_for_continuation(
        self,
        *,
        session: AgentSession,
        continuation: AgentContinuation,
        trace,
        started: float,
    ) -> ModelMessage | AgentRunResult:
        """按 continuation 定位 assistant(tool_calls) 消息。"""

        if continuation.assistant_message_index >= len(session.messages):
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=continuation.model_turns_used,
                tool_calls=continuation.tool_calls_used,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_CONTINUATION_INVALID,
                message="assistant_message_index is out of range",
                session=session,
            )
        assistant_message = session.messages[continuation.assistant_message_index]
        if assistant_message.role != "assistant":
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=continuation.model_turns_used,
                tool_calls=continuation.tool_calls_used,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_CONTINUATION_INVALID,
                message="continuation does not point to an assistant message",
                session=session,
            )
        if not assistant_message.tool_calls:
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=continuation.model_turns_used,
                tool_calls=continuation.tool_calls_used,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_CONTINUATION_INVALID,
                message="assistant message has no tool calls",
                session=session,
            )
        return assistant_message

    def _process_tool_calls(
        self,
        *,
        trace,
        state: _DriveState,
        is_resume: bool,
    ) -> AgentRunResult | None:
        """顺序处理当前 assistant message 的剩余 Tool Calls。

        该方法只会从 `state.next_tool_call_index` 开始，不会触碰已持久化的历史
        tool result。遇到新的 confirmation-required 工具时立即暂停并释放占用。
        """

        assistant_message = state.session.messages[state.current_assistant_message_index]
        tool_calls = tuple(assistant_message.tool_calls or ())
        if state.next_tool_call_index > len(tool_calls):
            return self._session_error_result(
                trace=trace,
                session_id=state.session.session_id,
                started=state.started,
                model_turns=state.model_turns,
                tool_calls=state.tool_calls,
                messages=tuple(state.session.messages),
                error_code=ERROR_SESSION_CONTINUATION_INVALID,
                message="next_tool_call_index is out of range",
                session=state.session,
            )
        remaining_count = len(tool_calls) - state.next_tool_call_index
        if remaining_count == 0:
            cleared = self._clear_completed_continuation(
                trace=trace,
                state=state,
            )
            if isinstance(cleared, AgentRunResult):
                return cleared
            state.current_assistant_message_index = None
            state.next_tool_call_index = 0
            state.current_originating_run_id = trace.run_id
            return None
        if state.tool_calls + remaining_count > self.limits.max_tool_calls:
            return self._limit_reached(
                trace=trace,
                session=state.session,
                started=state.started,
                model_turns=state.model_turns,
                tool_calls=state.tool_calls,
                messages=tuple(state.session.messages),
                error_code=ERROR_MAX_TOOL_CALLS_REACHED,
                message="Maximum tool calls reached before executing the current batch",
                limit_type="max_tool_calls",
                finish_reason=state.finish_reason,
            )
        if self._deadline_reached(state.active_deadline):
            return self._limit_reached(
                trace=trace,
                session=state.session,
                started=state.started,
                model_turns=state.model_turns,
                tool_calls=state.tool_calls,
                messages=tuple(state.session.messages),
                error_code=ERROR_TIMEOUT_REACHED,
                message="Agent run timed out before executing tools",
                limit_type="timeout",
                finish_reason=state.finish_reason,
            )

        self.trace_recorder.record_step(
            trace,
            "tool_batch_started",
            {
                "modelTurns": state.model_turns,
                "toolCallCount": state.tool_calls,
            },
        )
        for tool_call_index in range(state.next_tool_call_index, len(tool_calls)):
            tool_call = tool_calls[tool_call_index]
            if self._deadline_reached(state.active_deadline):
                return self._limit_reached(
                    trace=trace,
                    session=state.session,
                    started=state.started,
                    model_turns=state.model_turns,
                    tool_calls=state.tool_calls,
                    finish_reason=state.finish_reason,
                    messages=tuple(state.session.messages),
                    error_code=ERROR_TIMEOUT_REACHED,
                    message="Agent run timed out before executing a tool",
                    limit_type="timeout",
                )
            if is_resume:
                self.trace_recorder.record_step(
                    trace,
                    "tool_call_resumed",
                    {
                        "modelTurns": state.model_turns,
                        "toolCallCount": state.tool_calls,
                        "toolName": tool_call.name,
                    },
                )
            self.trace_recorder.record_step(
                trace,
                "tool_call_started",
                {
                    "modelTurns": state.model_turns,
                    "toolCallCount": state.tool_calls,
                    "toolName": tool_call.name,
                },
            )

            heartbeat_error = self._heartbeat_state_or_result(
                trace=trace,
                state=state,
                message="Session ownership heartbeat failed before tool preflight",
            )
            if heartbeat_error is not None:
                return heartbeat_error
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
                        session=state.session,
                        prepared_call=prepared_call,
                        assistant_message_index=state.current_assistant_message_index,
                        tool_call_index=tool_call_index,
                        model_turns=state.model_turns,
                        tool_calls=state.tool_calls,
                        started=state.started,
                        started_at=state.started_at,
                        deadline_at=state.deadline_at,
                        originating_run_id=state.current_originating_run_id or trace.run_id,
                        remaining_runtime_seconds=max(
                            0.0,
                            state.active_deadline - self.monotonic_provider(),
                        ),
                        ownership=_require_ownership(state.ownership),
                    )
                if decision.disposition == ToolDisposition.EXECUTE_NOW:
                    heartbeat_error = self._heartbeat_state_or_result(
                        trace=trace,
                        state=state,
                        message="Session ownership heartbeat failed before tool execution",
                    )
                    if heartbeat_error is not None:
                        return heartbeat_error
                    result = self.tool_executor.execute_prepared(prepared_call)
                    heartbeat_error = self._heartbeat_state_or_result(
                        trace=trace,
                        state=state,
                        message="Session ownership heartbeat failed after tool execution",
                    )
                    if heartbeat_error is not None:
                        return heartbeat_error
                else:
                    result = _policy_denied_result(
                        tool_call_id=prepared_call.tool_call_id,
                        tool_name=prepared_call.tool_name,
                        message=decision.message,
                    )

            state.tool_calls += 1
            state.next_tool_call_index = tool_call_index + 1
            try:
                state.session = self._append_tool_result_and_save(state, result)
            except SessionStoreError as exc:
                return self._session_error_result(
                    trace=trace,
                    session_id=state.session.session_id,
                    started=state.started,
                    model_turns=state.model_turns,
                    tool_calls=state.tool_calls,
                    finish_reason=state.finish_reason,
                    messages=tuple(state.session.messages),
                    error_code=_session_error_code(exc),
                    message="Session could not save tool result",
                    session=state.session,
                )

            self._record_tool_result(
                trace=trace,
                result=result,
                model_turns=state.model_turns,
                tool_calls=state.tool_calls,
            )

            if self._deadline_reached(state.active_deadline):
                return self._limit_reached(
                    trace=trace,
                    session=state.session,
                    started=state.started,
                    model_turns=state.model_turns,
                    tool_calls=state.tool_calls,
                    finish_reason=state.finish_reason,
                    messages=tuple(state.session.messages),
                    error_code=ERROR_TIMEOUT_REACHED,
                    message="Agent run timed out after executing a tool",
                    limit_type="timeout",
                )

        self.trace_recorder.record_step(
            trace,
            "tool_batch_completed",
            {
                "modelTurns": state.model_turns,
                "toolCallCount": state.tool_calls,
            },
        )
        cleared = self._clear_completed_continuation(trace=trace, state=state)
        if isinstance(cleared, AgentRunResult):
            return cleared
        state.current_assistant_message_index = None
        state.next_tool_call_index = 0
        state.current_originating_run_id = trace.run_id
        return None

    def _clear_completed_continuation(
        self,
        *,
        trace,
        state: _DriveState,
    ) -> AgentRunResult | None:
        """当前 assistant 的 Tool Calls 全部消费后清除旧 continuation。

        continuation 只描述暂停断点；一旦恢复批次完成，后续新 assistant 的工具调
        用必须以新的 run_id 和 assistant index 重新建立断点。
        """

        if state.session.continuation is None:
            return None
        state.session.continuation = None
        try:
            state.session = self._save_owned_session(
                state.session,
                _require_ownership(state.ownership),
            )
        except SessionStoreError as exc:
            return self._session_error_result(
                trace=trace,
                session_id=state.session.session_id,
                started=state.started,
                model_turns=state.model_turns,
                tool_calls=state.tool_calls,
                finish_reason=state.finish_reason,
                messages=tuple(state.session.messages),
                error_code=_session_error_code(exc),
                message="Session could not clear completed continuation",
                session=state.session,
            )
        return None

    def _append_tool_result_and_save(
        self,
        state: _DriveState,
        result: ToolExecutionResult,
    ) -> AgentSession:
        """追加 role=tool Result，并在 Resume 场景同步推进 continuation 游标。"""

        state.session.messages.append(_tool_result_message(result))
        if state.session.continuation is not None:
            state.session.continuation = replace(
                state.session.continuation,
                next_tool_call_index=state.next_tool_call_index,
                tool_calls_used=state.tool_calls,
                remaining_runtime_seconds=max(
                    0.0,
                    state.active_deadline - self.monotonic_provider(),
                ),
            )
        return self._save_owned_session(
            state.session,
            _require_ownership(state.ownership),
        )

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

        if session.status == AgentSessionStatus.RUNNING:
            error_code = (
                ERROR_SESSION_STALE_RUN_REQUIRES_RECOVERY
                if self._session_lease_expired(session, self._utc_now())
                else ERROR_SESSION_ALREADY_RUNNING
            )
            return self._session_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=0,
                tool_calls=0,
                messages=tuple(session.messages),
                error_code=error_code,
                message=(
                    "Session has a stale run that requires recovery"
                    if error_code == ERROR_SESSION_STALE_RUN_REQUIRES_RECOVERY
                    else "Session is already running"
                ),
                release_session=False,
            )
        if session.status not in (AgentSessionStatus.ACTIVE, AgentSessionStatus.COMPLETED):
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
        originating_run_id: str,
        remaining_runtime_seconds: float,
        ownership: RunOwnership,
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
            originating_run_id=originating_run_id,
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
                session=session,
            )

        session.status = AgentSessionStatus.WAITING_CONFIRMATION
        session.pending_action_id = action.action_id
        session.continuation = AgentContinuation(
            originating_run_id=originating_run_id,
            assistant_message_index=assistant_message_index,
            next_tool_call_index=tool_call_index,
            model_turns_used=model_turns,
            tool_calls_used=tool_calls,
            started_at=started_at,
            deadline_at=deadline_at,
            remaining_runtime_seconds=remaining_runtime_seconds,
        )
        finalized = self._finalize_owned_session(
            trace=trace,
            session=session,
            ownership=ownership,
            target_status=AgentSessionStatus.WAITING_CONFIRMATION,
            started=started,
            model_turns=model_turns,
            tool_calls=tool_calls,
        )
        if isinstance(finalized, AgentRunResult):
            return finalized
        session = finalized

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
        session: AgentSession | None = None,
        release_session: bool = True,
        ownership: RunOwnership | None = None,
    ) -> AgentRunResult:
        """构造会话一致性错误结果，统一 fail closed。"""

        if release_session and session is not None and session.status == AgentSessionStatus.RUNNING:
            finalized = self._finalize_owned_session(
                trace=trace,
                session=session,
                ownership=ownership or _ownership_from_session(session),
                target_status=AgentSessionStatus.FAILED,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
            )
            if isinstance(finalized, AgentRunResult):
                return finalized
            session = finalized
            messages = tuple(session.messages)
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

    def _finalize_owned_session(
        self,
        *,
        trace,
        session: AgentSession,
        ownership: RunOwnership,
        target_status: AgentSessionStatus,
        started: float,
        model_turns: int,
        tool_calls: int,
        finish_reason: str | None = None,
    ) -> AgentSession | AgentRunResult:
        """严格持久化当前 run 的终态，并在保存异常后做一次安全对账。

        这里是 `RUNNING / active_run_id` 的唯一释放边界。只有当前 run 仍拥有
        `active_run_id` 时才会清空 owner；如果 CAS 保存失败，会重新读取 Store
        判断“已提交但 ack 丢失”、确实未提交、owner 已变化或状态未知。任何无法确
        认的情况都返回稳定 finalization 错误，避免把未持久化的完成态伪装成成功。
        """

        if (
            session.active_run_id != ownership.run_id
            or session.run_fence_generation != ownership.fence_generation
        ):
            return self._finalization_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                messages=tuple(session.messages),
                error_code=ERROR_SESSION_RUN_FENCE_LOST,
                message="The agent run could not finalize because session ownership changed.",
                finish_reason=finish_reason,
            )

        expected_version = session.version
        session.status = target_status
        session.active_run_id = None
        session.active_run_last_heartbeat_at = None
        session.active_run_lease_expires_at = None
        if target_status != AgentSessionStatus.WAITING_CONFIRMATION:
            session.pending_action_id = None
            session.continuation = None
        try:
            return self._save_owned_session(session, ownership)
        except (SessionRunFenceLostError, SessionRunLeaseExpiredError) as exc:
            return self._finalization_error_result(
                trace=trace,
                session_id=session.session_id,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                messages=tuple(session.messages),
                error_code=_session_error_code(exc),
                message="The agent run could not finalize because session ownership changed.",
                finish_reason=finish_reason,
            )
        except SessionStoreError:
            return self._reconcile_finalization_failure(
                trace=trace,
                expected_session=session,
                ownership=ownership,
                expected_version=expected_version,
                target_status=target_status,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
            )

    def _reconcile_finalization_failure(
        self,
        *,
        trace,
        expected_session: AgentSession,
        ownership: RunOwnership,
        expected_version: int,
        target_status: AgentSessionStatus,
        started: float,
        model_turns: int,
        tool_calls: int,
        finish_reason: str | None,
    ) -> AgentSession | AgentRunResult:
        """保存抛错后的 read-after-failure 对账。

        真实持久化系统可能“提交成功但响应失败”。因此保存异常后只读取一次当前
        Session：若已是预期终态就接受该终态；若仍由当前 run 占用则明确失败；若
        owner 或版本已被其他执行者改变，则拒绝覆盖；若连读取都失败，则返回状态未知。
        """

        try:
            stored = self.session_store.get(expected_session.session_id)
        except SessionStoreError:
            return self._finalization_error_result(
                trace=trace,
                session_id=expected_session.session_id,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                messages=tuple(expected_session.messages),
                error_code=ERROR_SESSION_FINALIZATION_STATE_UNKNOWN,
                message=(
                    "The agent run finished locally, but the session finalization "
                    "state could not be confirmed."
                ),
                finish_reason=finish_reason,
            )

        if stored is None:
            return self._finalization_error_result(
                trace=trace,
                session_id=expected_session.session_id,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                messages=tuple(expected_session.messages),
                error_code=ERROR_SESSION_FINALIZATION_STATE_UNKNOWN,
                message=(
                    "The agent run finished locally, but the session finalization "
                    "state could not be confirmed."
                ),
                finish_reason=finish_reason,
            )

        if _session_matches_finalized_target(
            stored=stored,
            expected=expected_session,
            ownership=ownership,
            expected_version=expected_version,
            target_status=target_status,
        ):
            return stored

        if (
            stored.active_run_id == ownership.run_id
            and stored.run_fence_generation == ownership.fence_generation
        ):
            return self._finalization_error_result(
                trace=trace,
                session_id=expected_session.session_id,
                started=started,
                model_turns=model_turns,
                tool_calls=tool_calls,
                messages=tuple(stored.messages),
                error_code=ERROR_SESSION_FINALIZATION_PERSIST_FAILED,
                message=(
                    "The agent run finished locally, but the session state could "
                    "not be persisted."
                ),
                finish_reason=finish_reason,
            )

        return self._finalization_error_result(
            trace=trace,
            session_id=expected_session.session_id,
            started=started,
            model_turns=model_turns,
            tool_calls=tool_calls,
            messages=tuple(stored.messages),
            error_code=ERROR_SESSION_OWNERSHIP_LOST,
            message="The agent run could not finalize because session ownership changed.",
            finish_reason=finish_reason,
        )

    def _finalization_error_result(
        self,
        *,
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
        """返回安全的 finalization 错误，不泄露 Store 细节或尝试二次释放。"""

        self.trace_recorder.finish(trace, GENERIC_STATUS_FAILED)
        self.trace_recorder.record_step(
            trace,
            "session_finalization_failed",
            {
                "modelTurns": model_turns,
                "toolCallCount": tool_calls,
                "errorCode": error_code,
                "elapsedMs": self._elapsed_ms(started),
            },
        )
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
        session: AgentSession,
        started: float,
        model_turns: int,
        tool_calls: int,
        messages: tuple[ModelMessage, ...],
        error_code: str,
        message: str,
        limit_type: str,
        finish_reason: str | None = None,
    ) -> AgentRunResult:
        finalized = self._finalize_owned_session(
            trace=trace,
            session=session,
            ownership=_ownership_from_session(session),
            target_status=AgentSessionStatus.FAILED,
            started=started,
            model_turns=model_turns,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
        )
        if isinstance(finalized, AgentRunResult):
            return finalized
        session = finalized
        messages = tuple(session.messages)
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
            session_id=session.session_id,
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


def _tool_result_counts(messages: list[ModelMessage] | tuple[ModelMessage, ...]) -> dict[str, int]:
    """统计每个 tool_call_id 已持久化的 role=tool Result 数量。"""

    counts: dict[str, int] = {}
    for message in messages:
        if message.role == "tool" and message.tool_call_id:
            counts[message.tool_call_id] = counts.get(message.tool_call_id, 0) + 1
    return counts


def _session_matches_finalized_target(
    *,
    stored: AgentSession,
    expected: AgentSession,
    ownership: RunOwnership,
    expected_version: int,
    target_status: AgentSessionStatus,
) -> bool:
    """判断保存异常后的 read-back 是否已是当前 run 的目标终态。

    该判断刻意只比较外部可验证的不变量：目标状态、owner 已释放、消息历史、
    confirmation 指针和 continuation，以及 version 已经推进。它不比较 updated_at，
    因为不同 Store 会在提交时生成自己的更新时间。
    """

    return (
        stored.status == target_status
        and stored.active_run_id is None
        and stored.active_run_last_heartbeat_at is None
        and stored.active_run_lease_expires_at is None
        and stored.run_fence_generation == ownership.fence_generation
        and stored.pending_action_id == expected.pending_action_id
        and stored.continuation == expected.continuation
        and stored.messages == expected.messages
        and stored.version > expected_version
    )


def _ownership_from_session(session: AgentSession) -> RunOwnership:
    """从 RUNNING session 派生当前 ownership；不用于公开返回。"""

    return RunOwnership(
        session_id=session.session_id,
        run_id=session.active_run_id or "",
        fence_generation=session.run_fence_generation,
    )


def _require_ownership(ownership: RunOwnership | None) -> RunOwnership:
    if ownership is None:
        raise SessionRunFenceLostError("Session run ownership is missing")
    return ownership


def _positive_or_zero(value: float, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be non-negative") from exc
    if number < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return number


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

    if isinstance(exc, SessionRunFenceLostError):
        return ERROR_SESSION_RUN_FENCE_LOST
    if isinstance(exc, SessionRunLeaseExpiredError):
        return ERROR_SESSION_RUN_LEASE_EXPIRED
    if isinstance(exc, SessionVersionConflictError):
        return ERROR_SESSION_VERSION_CONFLICT
    return ERROR_SESSION_STATE_CONFLICT
