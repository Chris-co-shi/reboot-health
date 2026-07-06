"""Tool Executor 预留模块。

后续执行器负责根据 ToolContract 调用受控领域服务。当前阶段不执行任何外部副作用。
"""

from __future__ import annotations

from typing import Any

from agent.tools.registry import ToolRegistry


class ToolExecutor:
    """只允许执行已注册 Tool 的执行器骨架。"""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """当前阶段拒绝执行 Tool，避免误接外部副作用。"""
        if self.registry.get(name) is None:
            raise KeyError(f"Unsupported tool: {name}")
        raise NotImplementedError("Tool execution is not implemented in M2.5-B")
