"""Memory Manager 预留模块。

后续 Memory Manager 负责管理候选、证据窗口、样本数和确认流程；当前不做持久化。
"""

from __future__ import annotations

from typing import Any, Mapping

from agent.memory.candidate import MemoryCandidate


class MemoryCandidateBuilder:
    """从 Agent 输出中提取待确认记忆候选。"""

    def from_planning_output(self, output: Mapping[str, Any]) -> list[MemoryCandidate]:
        """从 INITIAL_PLANNING 输出生成候选，不保存事实。"""
        candidates: list[MemoryCandidate] = []
        candidates.extend(
            self._from_items(
                kind="understanding",
                items=output.get("understandingCandidates"),
            )
        )
        candidates.extend(
            self._from_items(
                kind="health_constraint",
                items=output.get("healthConstraintCandidates"),
            )
        )
        candidates.extend(
            self._from_items(
                kind="goal",
                items=output.get("goalCandidates"),
            )
        )
        return candidates

    def _from_items(self, kind: str, items: Any) -> list[MemoryCandidate]:
        """把候选列表转换为 MemoryCandidate。"""
        if not isinstance(items, list):
            return []
        candidates: list[MemoryCandidate] = []
        for item in items:
            content = dict(item) if isinstance(item, Mapping) else {"text": str(item)}
            evidence = [str(content.get("text") or content.get("name") or kind)]
            candidates.append(
                MemoryCandidate(
                    kind=kind,
                    content=content,
                    evidence=evidence,
                    confidence=str(content.get("confidence") or "low"),
                    requires_user_confirmation=True,
                )
            )
        return candidates


class MemoryManager:
    """内存中的候选收集器骨架。"""

    def __init__(self) -> None:
        self._candidates: list[MemoryCandidate] = []

    def add_candidate(self, candidate: MemoryCandidate) -> None:
        """记录一条候选，但不确认、不发布。"""
        self._candidates.append(candidate)

    def candidates(self) -> tuple[MemoryCandidate, ...]:
        """返回候选快照。"""
        return tuple(self._candidates)
