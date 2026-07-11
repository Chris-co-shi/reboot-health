"""AgentRunResult 外部合同。

AgentRunResult 是后续 FastAPI、真实模型和 Flutter 接入前的稳定运行结果形状。
它包装 Skill 原始输出，同时补充 run/session/trace/memory/error 等 Harness 元数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from agent.memory.candidate import MemoryCandidate
from agent.models import ModelMessage
from agent.runtime.trace import RunTrace
from agent.schemas.agent import AGENT_RUN_SCHEMA_VERSION


@dataclass(frozen=True)
class AgentRunError:
    """AgentRun 的结构化错误。"""

    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """返回可序列化错误。"""
        return {
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class PendingActionSummary:
    """等待确认动作的外部安全摘要。

    该结构面向 CLI/API 层展示，不携带完整 arguments、arguments_hash、Store version
    或 Provider 原始响应。真正的可执行快照只保存在 PendingActionStore 中。
    """

    action_id: str
    tool_name: str
    summary: str
    expires_at: datetime

    def to_dict(self) -> dict[str, str]:
        """返回可序列化的等待确认摘要。"""

        return {
            "actionId": self.action_id,
            "toolName": self.tool_name,
            "summary": self.summary,
            "expiresAt": self.expires_at.isoformat(),
        }


@dataclass(frozen=True)
class AgentRunResult:
    """一次 AgentLoop 运行的稳定结果合同。"""

    run_id: str
    session_id: str
    status: str
    selected_skill: str | None
    final_outcome: str
    output: Mapping[str, Any] | None
    trace: RunTrace
    memory_candidates: tuple[MemoryCandidate, ...] = ()
    warnings: tuple[str, ...] = ()
    quality_findings: tuple[Mapping[str, Any], ...] = ()
    error: AgentRunError | None = None
    schema_version: str = AGENT_RUN_SCHEMA_VERSION
    final_text: str | None = None
    messages: tuple[ModelMessage, ...] = ()
    model_turns: int = 0
    tool_calls: int = 0
    finish_reason: str | None = None
    pending_action: PendingActionSummary | None = None

    def to_dict(self) -> dict[str, Any]:
        """返回 API 友好的 camelCase 结构。"""
        return {
            "schemaVersion": self.schema_version,
            "runId": self.run_id,
            "sessionId": self.session_id,
            "status": self.status,
            "selectedSkill": self.selected_skill,
            "finalOutcome": self.final_outcome,
            "output": dict(self.output or {}),
            "memoryCandidates": [
                candidate.to_dict() for candidate in self.memory_candidates
            ],
            "trace": self.trace.to_dict(),
            "warnings": list(self.warnings),
            "qualityFindings": [
                dict(finding) for finding in self.quality_findings
            ],
            "error": self.error.to_dict() if self.error else None,
            "finalText": self.final_text,
            "messages": [_message_summary(message) for message in self.messages],
            "modelTurns": self.model_turns,
            "toolCalls": self.tool_calls,
            "finishReason": self.finish_reason,
            "pendingAction": (
                self.pending_action.to_dict()
                if self.pending_action is not None
                else None
            ),
        }


def _message_summary(message: ModelMessage) -> dict[str, Any]:
    """返回可序列化消息摘要，不暴露完整 prompt 或用户原文。"""
    content = message.content or ""
    result: dict[str, Any] = {
        "role": message.role,
        "hasContent": bool(content),
        "contentChars": len(content),
    }
    if message.name:
        result["name"] = message.name
    if message.tool_call_id:
        result["toolCallId"] = message.tool_call_id
    tool_calls = getattr(message, "tool_calls", ())
    if tool_calls:
        result["toolCallCount"] = len(tool_calls)
    return result
