"""Memory Candidate 定义。

MemoryCandidate 只是待确认记忆候选，不等于 confirmed memory，也不能直接影响计划
发布或健康约束。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MemoryCandidate:
    """一条待确认记忆候选。"""

    kind: str
    content: dict[str, Any]
    evidence: list[str] = field(default_factory=list)
    confidence: str = "low"
    requires_user_confirmation: bool = True

    def to_dict(self) -> dict[str, Any]:
        """返回可序列化候选结构。"""
        return {
            "kind": self.kind,
            "content": self.content,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "requiresUserConfirmation": self.requires_user_confirmation,
        }
