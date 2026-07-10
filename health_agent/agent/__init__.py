"""Python-first Health Agent Backend 的公共入口。

当前包只暴露最小 Agent Core、产品 Bootstrap、Skill Registry 和
INITIAL_PLANNING 兼容数据结构。这里保持窄出口，避免调用方依赖内部文件布局。
"""

from agent.bootstrap import create_agent_core_from_env, create_model_provider_from_env
from agent.runtime.core import AgentCore
from agent.schemas.planning import PlanningInput, PlanningOutput
from agent.skills.registry import SkillRegistry

__all__ = [
    "AgentCore",
    "PlanningInput",
    "PlanningOutput",
    "SkillRegistry",
    "create_agent_core_from_env",
    "create_model_provider_from_env",
]
