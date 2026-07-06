"""最小 Agent Loop。

本模块把 single-shot Skill 接入 Session、Context、Trace、ToolRegistry 和
MemoryCandidate 基础能力。它仍然不是完整自治 Agent：当前只允许有限步执行，不接
数据库、Redis、Web API、真实模型或任意外部工具。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from agent.memory.candidate import MemoryCandidate
from agent.memory.manager import MemoryCandidateBuilder
from agent.models.base import ProviderResponseError
from agent.models.mock import MockProvider
from agent.runtime.context import ContextBuilder
from agent.runtime.session import AgentSession, InMemorySessionStore
from agent.runtime.state import RunStatus
from agent.runtime.trace import RunTrace, TraceRecorder
from agent.schemas.planning import SchemaValidationError
from agent.skills.initial_planning import InitialPlanningSkill
from agent.skills.registry import SkillRegistry
from agent.tools.executor import ToolExecutor
from agent.tools.registry import ToolRegistry


CORE_RESULT_SCHEMA_VERSION = "health-agent.core.v0"


@dataclass(frozen=True)
class LoopLimits:
    """Agent Loop 的安全上限配置。"""

    max_steps: int = 1
    max_tool_calls: int = 0
    timeout_seconds: float = 30.0


class AgentLoop:
    """受限的 Agent Harness 运行循环。

    当前循环每次最多执行一个 Skill step。`max_steps` 仍然强制生效，用于防止后续
    扩展时出现无限自治。
    """

    def __init__(
        self,
        skill_registry: SkillRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        tool_executor: ToolExecutor | None = None,
        context_builder: ContextBuilder | None = None,
        session_store: InMemorySessionStore | None = None,
        trace_recorder: TraceRecorder | None = None,
        memory_candidate_builder: MemoryCandidateBuilder | None = None,
        limits: LoopLimits | None = None,
    ) -> None:
        self.skill_registry = skill_registry or SkillRegistry()
        self.tool_registry = tool_registry or ToolRegistry()
        self.tool_executor = tool_executor or ToolExecutor(self.tool_registry)
        self.context_builder = context_builder or ContextBuilder()
        self.session_store = session_store or InMemorySessionStore()
        self.trace_recorder = trace_recorder or TraceRecorder()
        self.memory_candidate_builder = (
            memory_candidate_builder or MemoryCandidateBuilder()
        )
        self.limits = limits or LoopLimits()
        self.last_session: AgentSession | None = None
        self.last_trace: RunTrace | None = None
        self.last_memory_candidates: tuple[MemoryCandidate, ...] = ()

    @classmethod
    def default(cls, provider: Any | None = None, limits: LoopLimits | None = None) -> "AgentLoop":
        """创建只注册 INITIAL_PLANNING 的默认循环。"""
        registry = SkillRegistry()
        registry.register(InitialPlanningSkill(provider=provider or MockProvider()))
        return cls(skill_registry=registry, limits=limits)

    def run(
        self,
        request: str | Mapping[str, Any],
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """运行一次 Agent 请求，并返回 Skill 兼容输出。"""
        trigger, skill_payload, session_id = self._normalize_request(request, payload)
        session = self.session_store.get_or_create(session_id=session_id)
        self.last_session = session
        trace = self.trace_recorder.start(
            session_id=session.session_id,
            trigger_type=trigger or "UNKNOWN",
            provider="mock",
        )
        self.last_trace = trace

        if self.limits.max_steps <= 0:
            session.status = RunStatus.FAILED
            trace.warnings.append("max_steps_exceeded")
            self.trace_recorder.finish(trace, "max_steps_exceeded")
            return self._max_steps_exceeded(trigger)

        skill = self.skill_registry.get(trigger)
        if skill is None:
            session.status = RunStatus.FAILED
            self.trace_recorder.finish(trace, "unsupported")
            return self._unsupported(trigger)

        trace.selected_skill = trigger
        session.status = RunStatus.RUNNING
        session.current_skill = trigger

        context = self.context_builder.build(trigger, skill_payload, session)
        session.context_summary = context.summary
        self.trace_recorder.record_step(
            trace,
            "context_built",
            {"contextSummary": context.summary},
        )

        try:
            session.turns += 1
            self.trace_recorder.record_step(
                trace,
                "skill_started",
                {"selectedSkill": trigger, "step": session.turns},
            )
            output = skill.run(context.skill_payload)
            self.last_memory_candidates = tuple(
                self.memory_candidate_builder.from_planning_output(output)
                if trigger == "INITIAL_PLANNING"
                else []
            )
            final_outcome = self._final_outcome_for(output)
            if final_outcome == "waiting_confirmation":
                session.status = RunStatus.WAITING_CONFIRMATION
                session.pending_confirmations.append(trigger)
            else:
                session.status = RunStatus.COMPLETED
            self.trace_recorder.finish(trace, final_outcome)
            return output
        except (ProviderResponseError, SchemaValidationError, ValueError) as exc:
            session.status = RunStatus.FAILED
            self.trace_recorder.finish(trace, "error")
            return self._skill_failed(trigger, exc)

    def _normalize_request(
        self,
        request: str | Mapping[str, Any],
        payload: Mapping[str, Any] | None,
    ) -> tuple[str, Mapping[str, Any], str | None]:
        """归一化宽松请求格式。"""
        if isinstance(request, str):
            return request.strip().upper(), payload or {}, None

        data = dict(request)
        trigger = str(
            data.get("trigger")
            or data.get("type")
            or data.get("intent")
            or ""
        ).strip().upper()
        skill_payload = data.get("input")
        if skill_payload is None:
            skill_payload = data.get("payload")
        if skill_payload is None:
            skill_payload = data.get("data")
        if skill_payload is None:
            skill_payload = {}
        if not isinstance(skill_payload, Mapping):
            raise ValueError("AgentLoop request input must be an object")
        session_id = data.get("sessionId") or data.get("session_id")
        return trigger, skill_payload, str(session_id) if session_id else None

    def _final_outcome_for(self, output: Mapping[str, Any]) -> str:
        """根据输出边界判断最终状态。"""
        if output.get("requiresUserConfirmation") is True:
            return "waiting_confirmation"
        return "completed"

    def _unsupported(self, trigger: str) -> dict[str, Any]:
        """返回未知 trigger 的兼容错误结构。"""
        return {
            "schemaVersion": CORE_RESULT_SCHEMA_VERSION,
            "trigger": trigger or "UNKNOWN",
            "status": "unsupported",
            "error": {
                "code": "UNSUPPORTED_TRIGGER",
                "message": f"Unsupported trigger: {trigger or 'UNKNOWN'}",
            },
            "requiresUserConfirmation": False,
        }

    def _max_steps_exceeded(self, trigger: str) -> dict[str, Any]:
        """返回 max_steps 阻断结果。"""
        return {
            "schemaVersion": CORE_RESULT_SCHEMA_VERSION,
            "trigger": trigger or "UNKNOWN",
            "status": "error",
            "error": {
                "code": "MAX_STEPS_EXCEEDED",
                "message": "AgentLoop stopped because max_steps was reached",
            },
            "requiresUserConfirmation": False,
        }

    def _skill_failed(self, trigger: str, exc: Exception) -> dict[str, Any]:
        """返回 Skill 失败的兼容错误结构。"""
        return {
            "schemaVersion": CORE_RESULT_SCHEMA_VERSION,
            "trigger": trigger,
            "status": "error",
            "error": {
                "code": "SKILL_FAILED",
                "message": str(exc),
            },
            "requiresUserConfirmation": False,
        }
