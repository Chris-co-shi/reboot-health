"""Tool Executor 预留模块。

后续执行器负责根据 ToolContract 调用受控领域服务。当前阶段不执行任何外部副作用。
"""

from __future__ import annotations

from typing import Any

from agent.tools.contract import ToolCall, ToolResult
from agent.tools.registry import ToolRegistry


class ToolExecutor:
    """只允许执行已注册 Tool 的执行器骨架。"""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(self, name: str, payload: dict[str, Any] | None = None) -> ToolResult:
        """只执行已注册 Tool；未注册 Tool 一律拒绝。"""
        definition = self.registry.get(name)
        if definition is None:
            raise KeyError(f"Unsupported tool: {name}")
        call = ToolCall(name=definition.name, payload=dict(payload or {}))
        if definition.handler is not None:
            if definition.risk_level != "mock":
                raise PermissionError(
                    "Only mock tool handlers are allowed in M2.5-B"
                )
            return definition.handler(call)
        return ToolResult(
            name=definition.name,
            status="noop",
            output={},
            requires_confirmation=definition.requires_confirmation,
        )
