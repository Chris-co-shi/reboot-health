"""通用模型回合循环的直接回答路径。"""

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

GENERIC_TRIGGER_TYPE = "GENERIC_AGENT"
GENERIC_STATUS_COMPLETED = "completed"
GENERIC_STATUS_MODEL_ERROR = "model_error"
GENERIC_STATUS_INVALID_RESPONSE = "invalid_response"
ERROR_MODEL_ERROR = "MODEL_ERROR"
ERROR_INVALID_RESPONSE = "INVALID_RESPONSE"
ERROR_TOOL_CALL_LOOP_NOT_IMPLEMENTED = "TOOL_CALL_LOOP_NOT_IMPLEMENTED"


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
    ) -> None:
        self.provider = provider
        self.limits = limits or GenericLoopLimits()
        self.session_store = session_store or InMemorySessionStore()
        self.trace_recorder = trace_recorder or TraceRecorder()
        self.now_provider = now_provider
        self.system_prompt_path = system_prompt_path or _default_system_prompt_path()

    def run(self, request: AgentRequest) -> AgentRunResult:
        """执行一次直接回答模型回合。"""
        started = time.monotonic()
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

        model_turns = 1
        self.trace_recorder.record_step(
            trace,
            "model_turn_started",
            {"modelTurns": model_turns, "toolCallCount": 0, "provider": provider_name},
        )
        try:
            response = self.provider.complete_turn(messages=tuple(messages), tools=())
        except ProviderResponseError as exc:
            trace.warnings.append(exc.safe_summary)
            self.trace_recorder.finish(trace, GENERIC_STATUS_MODEL_ERROR)
            self.trace_recorder.record_step(
                trace,
                "run_finished",
                {
                    "finalStatus": GENERIC_STATUS_MODEL_ERROR,
                    "modelTurns": model_turns,
                    "toolCallCount": 0,
                    "errorCode": ERROR_MODEL_ERROR,
                    "elapsedMs": _elapsed_ms(started),
                },
            )
            return self._result(
                trace=trace,
                session_id=session.session_id,
                status=GENERIC_STATUS_MODEL_ERROR,
                model_turns=model_turns,
                messages=tuple(messages),
                error=AgentRunError(code=ERROR_MODEL_ERROR, message=exc.safe_summary),
            )

        tool_call_count = len(response.tool_calls)
        self.trace_recorder.record_step(
            trace,
            "model_turn_completed",
            {
                "modelTurns": model_turns,
                "toolCallCount": tool_call_count,
                "finishReason": response.finish_reason,
                "contentChars": len(response.content or ""),
            },
        )

        if response.tool_calls:
            self.trace_recorder.finish(trace, GENERIC_STATUS_INVALID_RESPONSE)
            self.trace_recorder.record_step(
                trace,
                "run_finished",
                {
                    "finalStatus": GENERIC_STATUS_INVALID_RESPONSE,
                    "modelTurns": model_turns,
                    "toolCallCount": tool_call_count,
                    "errorCode": ERROR_TOOL_CALL_LOOP_NOT_IMPLEMENTED,
                    "elapsedMs": _elapsed_ms(started),
                },
            )
            return self._result(
                trace=trace,
                session_id=session.session_id,
                status=GENERIC_STATUS_INVALID_RESPONSE,
                model_turns=model_turns,
                tool_calls=tool_call_count,
                finish_reason=response.finish_reason,
                messages=tuple(messages),
                error=AgentRunError(
                    code=ERROR_TOOL_CALL_LOOP_NOT_IMPLEMENTED,
                    message="Tool call loop is not implemented in Slice 4A",
                ),
            )

        final_text = str(response.content or "").strip()
        if not final_text:
            self.trace_recorder.finish(trace, GENERIC_STATUS_INVALID_RESPONSE)
            self.trace_recorder.record_step(
                trace,
                "run_finished",
                {
                    "finalStatus": GENERIC_STATUS_INVALID_RESPONSE,
                    "modelTurns": model_turns,
                    "toolCallCount": 0,
                    "errorCode": ERROR_INVALID_RESPONSE,
                    "elapsedMs": _elapsed_ms(started),
                },
            )
            return self._result(
                trace=trace,
                session_id=session.session_id,
                status=GENERIC_STATUS_INVALID_RESPONSE,
                model_turns=model_turns,
                finish_reason=response.finish_reason,
                messages=tuple(messages),
                error=AgentRunError(
                    code=ERROR_INVALID_RESPONSE,
                    message="Model response content is empty",
                ),
            )

        messages.append(ModelMessage(role="assistant", content=final_text))
        self.trace_recorder.finish(trace, GENERIC_STATUS_COMPLETED)
        self.trace_recorder.record_step(
            trace,
            "run_finished",
            {
                "finalStatus": GENERIC_STATUS_COMPLETED,
                "modelTurns": model_turns,
                "toolCallCount": 0,
                "finishReason": response.finish_reason,
                "elapsedMs": _elapsed_ms(started),
            },
        )
        return self._result(
            trace=trace,
            session_id=session.session_id,
            status=GENERIC_STATUS_COMPLETED,
            model_turns=model_turns,
            finish_reason=response.finish_reason,
            messages=tuple(messages),
            final_text=final_text,
            output={"finalText": final_text},
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


def _default_system_prompt_path() -> Path:
    return Path(__file__).resolve().parents[2] / "prompts" / "agent_system.zh-CN.md"


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
