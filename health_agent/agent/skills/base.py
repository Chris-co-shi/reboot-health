"""Skill 基础协议。

Skill 是 Health Agent 能力扩展的主要方式。Core 只依赖这个最小协议，不依赖
具体技能实现，从而保持 narrow waist。
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol


class Skill(Protocol):
    """所有运行时 Skill 必须满足的最小协议。"""

    trigger: str

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """执行 Skill，并返回 JSON-like 结果。"""
        ...
