"""产品运行组装入口。

本模块是唯一产品 Composition Root。默认产品入口使用通用 GenericAgentLoop；
INITIAL_PLANNING 仍保留为显式 legacy compatibility 工厂。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.config import load_llm_settings_from_env
from agent.models import ModelProvider, OpenAICompatibleProvider
from agent.runtime.confirmation_coordinator import ConfirmationCoordinator
from agent.runtime.core import AgentCore
from agent.runtime.generic_loop import GenericAgentLoop
from agent.runtime.pending_action_store import (
    InMemoryPendingActionStore,
    PendingActionStore,
)
from agent.runtime.session import InMemorySessionStore, SessionStore
from agent.runtime.storage import JsonFilePendingActionStore, JsonFileSessionStore
from agent.skills.initial_planning import InitialPlanningSkill
from agent.skills.registry import SkillRegistry
from agent.tools.builtin.convert_weight import create_convert_weight_unit_tool
from agent.tools.approved_executor import ApprovedActionExecutor
from agent.tools.executor import ToolExecutor
from agent.tools.registry import ToolRegistry


@dataclass(frozen=True)
class GenericRuntimeComponents:
    """产品 Generic Runtime 的共享组件集合。"""

    loop: GenericAgentLoop
    confirmation_coordinator: ConfirmationCoordinator
    session_store: SessionStore
    pending_action_store: PendingActionStore
    tool_registry: ToolRegistry
    tool_executor: ToolExecutor
    approved_action_executor: ApprovedActionExecutor


def create_model_provider_from_env(dotenv_path: Path | None = None) -> ModelProvider:
    """加载产品 LLM 配置并创建唯一产品模型 Provider。"""
    settings = load_llm_settings_from_env(dotenv_path=dotenv_path)
    return OpenAICompatibleProvider(settings=settings)


def create_generic_agent_loop_from_env(
    dotenv_path: Path | None = None,
    *,
    storage_mode: str = "memory",
    storage_directory: Path | str | None = None,
    run_lease_ttl_seconds: float | None = None,
    run_lease_heartbeat_interval_seconds: float | None = None,
    lease_safety_margin_seconds: float = 5.0,
) -> GenericAgentLoop:
    """创建默认产品 GenericAgentLoop，并注册正式只读内置工具。"""
    return create_generic_runtime_components_from_env(
        dotenv_path=dotenv_path,
        storage_mode=storage_mode,
        storage_directory=storage_directory,
        run_lease_ttl_seconds=run_lease_ttl_seconds,
        run_lease_heartbeat_interval_seconds=run_lease_heartbeat_interval_seconds,
        lease_safety_margin_seconds=lease_safety_margin_seconds,
    ).loop


def create_generic_runtime_components_from_env(
    dotenv_path: Path | None = None,
    *,
    storage_mode: str = "memory",
    storage_directory: Path | str | None = None,
    run_lease_ttl_seconds: float | None = None,
    run_lease_heartbeat_interval_seconds: float | None = None,
    lease_safety_margin_seconds: float = 5.0,
) -> GenericRuntimeComponents:
    """创建共享 Store/Registry 的 Generic Runtime 组件。

    当前产品入口仍只暴露 loop；后续 CLI/API 接入确认决策时应使用这里返回的
    confirmation_coordinator，避免与 loop 创建独立 Store。默认 storage_mode 仍是
    memory；JSON Store 必须由调用方显式传入目录启用，避免无意改变现有产品路径。
    """
    provider = create_model_provider_from_env(dotenv_path=dotenv_path)
    registry = ToolRegistry([create_convert_weight_unit_tool()])
    executor = ToolExecutor(registry)
    # 产品 Composition Root 显式注入 runtime store，避免 GenericAgentLoop 内部偷偷
    # 创建第二套状态依赖；持久化实现只在这里按显式配置替换。
    session_store, pending_action_store = _create_runtime_stores(
        storage_mode=storage_mode,
        storage_directory=storage_directory,
    )
    approved_action_executor = ApprovedActionExecutor(
        pending_action_store=pending_action_store,
        tool_registry=registry,
    )
    loop = GenericAgentLoop(
        provider=provider,
        session_store=session_store,
        tool_registry=registry,
        tool_executor=executor,
        pending_action_store=pending_action_store,
        run_lease_ttl_seconds=run_lease_ttl_seconds,
        run_lease_heartbeat_interval_seconds=run_lease_heartbeat_interval_seconds,
        lease_safety_margin_seconds=lease_safety_margin_seconds,
    )
    coordinator = ConfirmationCoordinator(
        session_store=session_store,
        pending_action_store=pending_action_store,
        tool_registry=registry,
        approved_action_executor=approved_action_executor,
    )
    return GenericRuntimeComponents(
        loop=loop,
        confirmation_coordinator=coordinator,
        session_store=session_store,
        pending_action_store=pending_action_store,
        tool_registry=registry,
        tool_executor=executor,
        approved_action_executor=approved_action_executor,
    )


def create_agent_core_from_env(dotenv_path: Path | None = None) -> AgentCore:
    """创建 INITIAL_PLANNING legacy compatibility AgentCore。"""
    provider = create_model_provider_from_env(dotenv_path=dotenv_path)
    registry = SkillRegistry([InitialPlanningSkill(provider=provider)])
    return AgentCore(registry=registry)


def _create_runtime_stores(
    *,
    storage_mode: str,
    storage_directory: Path | str | None,
) -> tuple[SessionStore, PendingActionStore]:
    """按显式存储模式创建 Runtime Store。

    这里故意不读取环境变量：Slice 5A 只建立可注入的 JSON Adapter，不改变任何
    默认运行行为。后续接入 CLI/API 时可以在上层决定目录、加密和部署策略。
    """

    normalized_mode = str(storage_mode or "memory").strip().lower()
    if normalized_mode == "memory":
        return InMemorySessionStore(), InMemoryPendingActionStore()
    if normalized_mode == "json":
        if storage_directory is None:
            raise ValueError("storage_directory is required when storage_mode='json'")
        directory = Path(storage_directory)
        return JsonFileSessionStore(directory), JsonFilePendingActionStore(directory)
    raise ValueError(f"Unsupported storage_mode: {storage_mode!r}")
