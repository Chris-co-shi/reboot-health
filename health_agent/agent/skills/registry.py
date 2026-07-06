"""Skill Registry：Agent Core 调用能力扩展的唯一入口。

当前 Registry 只管理 Skill，后续 Tool Registry 应保持独立，并继续执行白名单
注册和权限边界。Core 通过 Registry 取能力，避免把具体 Skill 写死进运行流程。
"""

from __future__ import annotations

from typing import Mapping

from agent.skills.base import Skill


class SkillRegistry:
    """按 trigger 管理运行时 Skill 的内存注册表。"""

    def __init__(self, skills: list[Skill] | None = None) -> None:
        """创建注册表，并注册传入的初始 Skill 列表。"""
        self._skills: dict[str, Skill] = {}
        for skill in skills or []:
            self.register(skill)

    def register(self, skill: Skill) -> None:
        """注册或覆盖一个 Skill。

        trigger 会统一去空白并转为大写，保证调用方大小写差异不会影响分发。
        """
        trigger = str(skill.trigger).strip().upper()
        if not trigger:
            raise ValueError("Skill trigger must not be empty")
        self._skills[trigger] = skill

    def get(self, trigger: str) -> Skill | None:
        """按 trigger 查找 Skill；不存在时返回 None。"""
        return self._skills.get(str(trigger).strip().upper())

    def dispatch(self, trigger: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """直接分发到 Skill；未知 trigger 通过 KeyError 暴露给内部调用方。"""
        skill = self.get(trigger)
        if skill is None:
            raise KeyError(f"Unsupported trigger: {trigger}")
        return skill.run(payload)

    @property
    def triggers(self) -> tuple[str, ...]:
        """返回已注册 trigger 的稳定排序快照，方便测试和诊断。"""
        return tuple(sorted(self._skills))
