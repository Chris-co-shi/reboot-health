"""Memory Schema 预留模块。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryCandidateSchema:
    """记忆候选的传输结构。"""

    text: str
    source: str
    confidence: str
