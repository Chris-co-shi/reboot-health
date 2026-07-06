"""Tool Registry 预留模块。

所有 Tool 必须先注册到这里，Agent Loop 后续只能调用白名单 Tool。
"""

from __future__ import annotations

from agent.tools.contract import ToolDefinition


class ToolRegistry:
    """按名称管理 ToolDefinition 的内存注册表。"""

    def __init__(self, definitions: list[ToolDefinition] | None = None) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        for definition in definitions or []:
            self.register(definition)

    def register(self, definition: ToolDefinition) -> None:
        """注册 ToolDefinition；名称为空时拒绝。"""
        name = definition.name.strip()
        if not name:
            raise ValueError("Tool name must not be empty")
        self._definitions[name] = definition

    def get(self, name: str) -> ToolDefinition | None:
        """按名称查找 ToolDefinition。"""
        return self._definitions.get(name.strip())

    def list(self) -> tuple[ToolDefinition, ...]:
        """返回已注册 ToolDefinition 的稳定排序快照。"""
        return tuple(self._definitions[name] for name in sorted(self._definitions))
