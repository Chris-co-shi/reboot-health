"""产品运行组装入口。

当前阶段只组装真实 OpenAI-compatible Provider 和 INITIAL_PLANNING 兼容 Skill。
测试替身不得从这里加载，产品路径也不会静默回退到测试 Provider。
"""

from __future__ import annotations

from pathlib import Path

from agent.config import load_llm_settings_from_env
from agent.models import ModelProvider, OpenAICompatibleProvider
from agent.runtime.core import AgentCore
from agent.skills.initial_planning import InitialPlanningSkill
from agent.skills.registry import SkillRegistry


def create_model_provider_from_env(dotenv_path: Path | None = None) -> ModelProvider:
    """加载产品 LLM 配置并创建唯一产品模型 Provider。"""
    settings = load_llm_settings_from_env(dotenv_path=dotenv_path)
    return OpenAICompatibleProvider(settings=settings)


def create_agent_core_from_env(dotenv_path: Path | None = None) -> AgentCore:
    """创建产品 AgentCore，并注入真实模型 Provider。"""
    provider = create_model_provider_from_env(dotenv_path=dotenv_path)
    registry = SkillRegistry([InitialPlanningSkill(provider=provider)])
    return AgentCore(registry=registry)
