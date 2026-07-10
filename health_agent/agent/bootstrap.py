"""产品运行组装入口。

本模块是唯一产品 Composition Root。默认产品入口使用通用 GenericAgentLoop；
INITIAL_PLANNING 仍保留为显式 legacy compatibility 工厂。
"""

from __future__ import annotations

from pathlib import Path

from agent.config import load_llm_settings_from_env
from agent.models import ModelProvider, OpenAICompatibleProvider
from agent.runtime.core import AgentCore
from agent.runtime.generic_loop import GenericAgentLoop
from agent.skills.initial_planning import InitialPlanningSkill
from agent.skills.registry import SkillRegistry
from agent.tools.builtin.convert_weight import create_convert_weight_unit_tool
from agent.tools.executor import ToolExecutor
from agent.tools.registry import ToolRegistry


def create_model_provider_from_env(dotenv_path: Path | None = None) -> ModelProvider:
    """加载产品 LLM 配置并创建唯一产品模型 Provider。"""
    settings = load_llm_settings_from_env(dotenv_path=dotenv_path)
    return OpenAICompatibleProvider(settings=settings)


def create_generic_agent_loop_from_env(dotenv_path: Path | None = None) -> GenericAgentLoop:
    """创建默认产品 GenericAgentLoop，并注册正式只读内置工具。"""
    provider = create_model_provider_from_env(dotenv_path=dotenv_path)
    registry = ToolRegistry([create_convert_weight_unit_tool()])
    executor = ToolExecutor(registry)
    return GenericAgentLoop(
        provider=provider,
        tool_registry=registry,
        tool_executor=executor,
    )


def create_agent_core_from_env(dotenv_path: Path | None = None) -> AgentCore:
    """创建 INITIAL_PLANNING legacy compatibility AgentCore。"""
    provider = create_model_provider_from_env(dotenv_path=dotenv_path)
    registry = SkillRegistry([InitialPlanningSkill(provider=provider)])
    return AgentCore(registry=registry)
