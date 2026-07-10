"""Run Trace。

Trace 只记录可审计摘要、策略判断和失败分类，不记录完整健康原文或认证信息。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


TRACE_STEP_ALLOWED_FIELDS = {
    "name",
    "status",
    "elapsedMs",
    "provider",
    "model",
    "topLevelKeys",
    "fieldTypes",
    "warningCount",
    "qualityWarningCount",
    "qualityErrorCount",
    "todayActionDraftSource",
    "todayActionDraftMissingFields",
    "payloadBytes",
    "contentChars",
    "selectedSkill",
    "step",
    "memoryCandidateCount",
    "modelTurns",
    "toolCallCount",
    "finishReason",
    "errorCode",
    "finalStatus",
}


@dataclass
class RunTrace:
    """一次 AgentRun 的最小追踪摘要。"""

    run_id: str
    session_id: str
    trigger_type: str
    provider: str
    selected_skill: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    final_outcome: str | None = None
    warnings: list[str] = field(default_factory=list)
    quality_findings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """返回外部可断言的 camelCase trace 结构。"""
        return {
            "runId": self.run_id,
            "sessionId": self.session_id,
            "triggerType": self.trigger_type,
            "selectedSkill": self.selected_skill,
            "steps": self.steps,
            "toolCalls": self.tool_calls,
            "finalOutcome": self.final_outcome,
            "warnings": self.warnings,
            "qualityFindings": self.quality_findings,
            "provider": self.provider,
        }


class TraceRecorder:
    """记录 AgentLoop 运行摘要的内存 recorder。"""

    def __init__(self) -> None:
        self._traces: list[RunTrace] = []

    def start(
        self,
        session_id: str,
        trigger_type: str,
        provider: str = "unknown",
    ) -> RunTrace:
        """开始一条新的 RunTrace。"""
        trace = RunTrace(
            run_id=f"run-{uuid4().hex}",
            session_id=session_id,
            trigger_type=trigger_type,
            provider=provider,
        )
        self._traces.append(trace)
        return trace

    def record_step(self, trace: RunTrace, name: str, detail: dict[str, Any]) -> None:
        """记录一个运行步骤。"""
        trace.steps.append(_sanitize_step(name, detail))

    def record_tool_call(self, trace: RunTrace, call: dict[str, Any]) -> None:
        """记录一次 Tool 调用摘要。"""
        trace.tool_calls.append(call)

    def finish(self, trace: RunTrace, final_outcome: str) -> None:
        """标记最终结果。"""
        trace.final_outcome = final_outcome

    def last(self) -> RunTrace | None:
        """返回最近一条 trace。"""
        if not self._traces:
            return None
        return self._traces[-1]

    def all(self) -> tuple[RunTrace, ...]:
        """返回 trace 快照。"""
        return tuple(self._traces)


def _sanitize_step(name: str, detail: dict[str, Any]) -> dict[str, Any]:
    """只保留 trace step 的结构化摘要字段。"""
    payload = {"name": name, "status": "ok", "elapsedMs": 0, **dict(detail or {})}
    return {
        key: _sanitize_value(value)
        for key, value in payload.items()
        if key in TRACE_STEP_ALLOWED_FIELDS
    }


def _sanitize_value(value: Any) -> Any:
    """限制 trace 值的形状，避免误记录大段文本或凭据。"""
    if isinstance(value, dict):
        return {
            str(key): _sanitize_value(item)
            for key, item in value.items()
            if not _is_sensitive_key(str(key))
        }
    if isinstance(value, list | tuple):
        return [_sanitize_value(item) for item in value[:50]]
    if isinstance(value, str):
        return _redact_text(value)[:180]
    return value


def _is_sensitive_key(key: str) -> bool:
    """识别不允许进入 trace 的字段名。"""
    normalized = key.lower().replace("-", "_")
    return (
        normalized in {
            "api_key",
            "apikey",
            "authorization",
            "auth_token",
            "access_token",
            "refresh_token",
            "token",
            "secret",
            "client_secret",
            "password",
            "prompt",
            "user_text",
            "usertext",
            "response",
            "content",
        }
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
    )


def _redact_text(value: str) -> str:
    """移除常见认证片段。"""
    text = value.replace("Bearer ", "Bearer <redacted> ")
    if "sk-" in text:
        return "sk-<redacted>"
    return text
