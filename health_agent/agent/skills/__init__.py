"""Skill 包公共导出。

新增健康能力应优先以独立 Skill 形式加入，并通过 Registry 注册，而不是把能力
堆进 Agent Core。
"""

from agent.skills.initial_planning import InitialPlanningSkill
from agent.skills.registry import SkillRegistry

__all__ = ["InitialPlanningSkill", "SkillRegistry"]
