"""Context Builder 预留模块。

Context Builder 后续只组装当前任务必要上下文，不加载完整数据库或全部聊天历史。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextSnapshot:
    """传给 Skill/Provider 的最小上下文快照。"""

    summary: str = ""
    facts: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
