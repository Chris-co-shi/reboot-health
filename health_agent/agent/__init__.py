"""Python-first Health Agent Backend 的公共入口。

当前包只暴露 M2.5 阶段已经落位的最小 Agent Core、Skill Registry 和
INITIAL_PLANNING 数据结构。这里保持窄出口，避免调用方依赖内部文件布局。
"""

from agent.runtime.core import AgentCore
from agent.schemas.planning import PlanningInput, PlanningOutput
from agent.skills.registry import SkillRegistry

__all__ = [
    "AgentCore",
    "PlanningInput",
    "PlanningOutput",
    "SkillRegistry",
]
