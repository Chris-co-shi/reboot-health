"""Run Trace 预留模块。

Trace 只记录可审计摘要、策略判断和失败分类，不记录完整健康原文或认证信息。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RunTrace:
    """一次 AgentRun 的最小追踪摘要。"""

    run_id: str
    trigger: str
    provider: str
    events: list[dict[str, Any]] = field(default_factory=list)
