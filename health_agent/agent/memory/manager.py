"""Memory Manager 预留模块。

后续 Memory Manager 负责管理候选、证据窗口、样本数和确认流程；当前不做持久化。
"""

from __future__ import annotations

from agent.memory.candidate import MemoryCandidate


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
