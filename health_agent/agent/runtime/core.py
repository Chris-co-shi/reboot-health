"""Agent Core v0：Health Agent 的窄腰调度层。

本模块只负责把外部触发请求规范化、按 trigger 找到已注册 Skill，并把执行
结果以稳定结构返回。它不保存健康事实、不连接数据库、不直接调用外部资源，
也不把模型输出升级为确认事实。
"""

from __future__ import annotations

from typing import Any, Mapping

from agent.models.mock import MockProvider
from agent.runtime.loop import AgentLoop
from agent.skills.initial_planning import InitialPlanningSkill
from agent.skills.registry import SkillRegistry


AGENT_CORE_SCHEMA_VERSION = "health-agent.core.v0"


class AgentCore:
    """只按 trigger 分发 Skill 的薄核心。

    Core 是 narrow waist：它知道如何注册和调用 Skill，但不内置具体健康能力。
    新能力应优先扩展 Skill，而不是膨胀这个调度层。
    """

    def __init__(self, registry: SkillRegistry | None = None) -> None:
        """创建 Core，并允许测试或上层运行时注入自定义 SkillRegistry。"""
        self.registry = registry or SkillRegistry()
        self.last_loop: AgentLoop | None = None

    @classmethod
    def default(cls, provider: Any | None = None) -> "AgentCore":
        """创建当前阶段默认 Core。

        默认只注册 INITIAL_PLANNING，Provider 默认为 MockProvider，保证本地测试
        不依赖真实模型、网络或外部凭据。
        """
        registry = SkillRegistry()
        registry.register(InitialPlanningSkill(provider=provider or MockProvider()))
        return cls(registry=registry)

    def run(
        self,
        trigger_or_request: str | Mapping[str, Any],
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行一次触发请求，并返回可序列化的结果字典。

        `trigger_or_request` 兼容两种输入：直接传 trigger 字符串，或传包含
        trigger/type/intent 与 input/payload/data 的请求对象。异常被收敛成
        结构化错误，避免把 Provider 或 Schema 细节泄漏给调用方。
        """
        loop = AgentLoop(skill_registry=self.registry)
        self.last_loop = loop
        return loop.run(trigger_or_request, payload)

    def _normalize_request(
        self,
        trigger_or_request: str | Mapping[str, Any],
        payload: Mapping[str, Any] | None,
    ) -> tuple[str, Mapping[str, Any]]:
        """把宽松请求格式压缩成 Core 内部唯一使用的 trigger/payload 形式。"""
        if isinstance(trigger_or_request, str):
            return trigger_or_request.strip().upper(), payload or {}

        request = dict(trigger_or_request)
        # 兼容不同调用方的命名，但进入 Registry 前统一大写，保证查找稳定。
        trigger = str(
            request.get("trigger")
            or request.get("type")
            or request.get("intent")
            or ""
        ).strip().upper()
        skill_payload = request.get("input")
        if skill_payload is None:
            skill_payload = request.get("payload")
        if skill_payload is None:
            skill_payload = request.get("data")
        if skill_payload is None:
            skill_payload = {}
        if not isinstance(skill_payload, Mapping):
            raise ValueError("AgentCore request input must be an object")
        return trigger, skill_payload

    def _unsupported(self, trigger: str) -> dict[str, Any]:
        """返回未知 trigger 的稳定错误结构。"""
        return {
            "schemaVersion": AGENT_CORE_SCHEMA_VERSION,
            "trigger": trigger or "UNKNOWN",
            "status": "unsupported",
            "error": {
                "code": "UNSUPPORTED_TRIGGER",
                "message": f"Unsupported trigger: {trigger or 'UNKNOWN'}",
            },
            "requiresUserConfirmation": False,
        }
