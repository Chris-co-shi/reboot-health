"""Memory Candidate 定义。

MemoryCandidate 只是待确认记忆候选，不等于 confirmed memory，也不能直接影响计划
发布或健康约束。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryCandidate:
    """一条待确认记忆候选。"""

    text: str
    source: str
    confidence: str = "low"
    sample_count: int = 1
