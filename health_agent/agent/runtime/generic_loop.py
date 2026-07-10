"""通用模型回合循环。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from agent.models import ModelMessage, ModelProvider, ProviderResponseError
from agent.models.base import freeze_mapping
from agent.runtime.context import build_runtime_environment
from agent.runtime.result import AgentRunError, AgentRunResult
from agent.runtime.session import InMemorySessionStore
from agent.runtime.trace import TraceRecorder
from agent.tools.executor import ToolExecutor
from agent.tools.registry import ToolRegistry

GENERIC_TRIGGER_TYPE = "GENERIC_AGENT"
GENERIC_STATUS_COMPLETED = "completed"
GENERIC_STATUS_MODEL_ERROR = "model_error"
GENERIC_STATUS_INVALID_RESPONSE = "invalid_response"
GENERIC_STATUS_LIMIT_REACHED = "limit_reached"
ERROR_MODEL_ERROR = "MODEL_ERROR"
ERROR_INVALID_RESPONSE = "INVALID_RESPONSE"
ERROR_MAX_MODEL_TURNS_REACHED = "MAX_MODEL_TURNS_REACHED"
ERROR_MAX_TOOL_CALLS_REACHED = "MAX_TOOL_CALLS_REACHED"
ERROR_TIMEOUT_REACHED = "TIMEOUT_REACHED"


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
        monotonic_provider: Callable[[], float] | None = None,
    ) -> None:
        self.provider = provider
        self.limits = limits or GenericLoopLimits()
        self.session_store = session_store or InMemorySessionStore()
        self.trace_recorder = trace_recorder or TraceRecorder()
        self.now_provider = now_provider
        self.system_prompt_path = system_prompt_path or _default_system_prompt_path()
        self.tool_registry = self._resolve_tool_registry(tool_registry, tool_executor)
        self.tool_executor = self._resolve_tool_executor(self.tool_registry, tool_executor)
        self.monotonic_provider = monotonic_provider or time.monotonic

    def run(self, request: AgentRequest) -> AgentRunResult:
        """执行一次有限模型回合循环。"""
        started = self.monotonic_provider()
        deadline = started + self.limits.timeout_seconds
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

        runtime_environment = build_runtime_environment(
            now=self.now_provider() if self.now_provider else None,
            locale=request.locale,
        )
        messages = self._build_initial_messages(request, runtime_environment.to_provider_payload())
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
                    messages=tuple(messages),
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
                    messages=tuple(messages),
                    tools=tool_definitions,
                )
            except ProviderResponseError as exc:
                trace.warnings.append(exc.safe_summary)
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
                    messages=tuple(messages),
                    error=AgentRunError(code=ERROR_MODEL_ERROR, message=exc.safe_summary),
                )

            messages.append(
                ModelMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
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
                    messages=tuple(messages),
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
                        messages=tuple(messages),
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
                        messages=tuple(messages),
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
                        messages=tuple(messages),
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
                for tool_call in response.tool_calls:
                    if self._deadline_reached(deadline):
                        return self._limit_reached(
                            trace=trace,
                            session_id=session.session_id,
                            started=started,
                            model_turns=model_turns,
                            tool_calls=tool_calls,
                            finish_reason=response.finish_reason,
                            messages=tuple(messages),
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
                    result = self.tool_executor.execute(tool_call)
                    tool_calls += 1
                    messages.append(
                        ModelMessage(
                            role="tool",
                            tool_call_id=result.tool_call_id,
                            name=result.tool_name,
                            content=result.content,
                        )
                    )
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

                    if self._deadline_reached(deadline):
                        return self._limit_reached(
                            trace=trace,
                            session_id=session.session_id,
                            started=started,
                            model_turns=model_turns,
                            tool_calls=tool_calls,
                            finish_reason=response.finish_reason,
                            messages=tuple(messages),
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
                    messages=tuple(messages),
                    error=AgentRunError(
                        code=ERROR_INVALID_RESPONSE,
                        message="Model response content is empty",
                    ),
                )

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
                messages=tuple(messages),
                final_text=final_text,
                output={"finalText": final_text},
            )

        return self._limit_reached(
            trace=trace,
            session_id=session.session_id,
            started=started,
            model_turns=model_turns,
            tool_calls=tool_calls,
            messages=tuple(messages),
            error_code=ERROR_MAX_MODEL_TURNS_REACHED,
            message="Maximum model turns reached",
            limit_type="max_model_turns",
        )

    def _build_initial_messages(
        self,
        request: AgentRequest,
        runtime_environment_payload: Mapping[str, str],
    ) -> list[ModelMessage]:
        prompt = self.system_prompt_path.read_text(encoding="utf-8").strip()
        runtime_context = json.dumps(
            {"runtimeEnvironment": dict(runtime_environment_payload)},
            ensure_ascii=False,
            sort_keys=True,
        )
        return [
            ModelMessage(
                role="system",
                content=f"{prompt}\n\nRuntime Environment:\n{runtime_context}",
            ),
            ModelMessage(role="user", content=request.user_text),
        ]

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
    return Path(__file__).resolve().parents[2] / "prompts" / "agent_system.zh-CN.md"
