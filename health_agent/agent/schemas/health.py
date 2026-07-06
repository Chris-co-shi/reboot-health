"""健康领域 Schema 预留模块。

AI 输出的健康信息只能是候选；确认事实仍由 Java Domain Kernel 或后续受控 Domain
Service 管理。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthConstraintCandidate:
    """健康约束候选。"""

    name: str
    rationale: str
    requires_user_confirmation: bool = True
