"""Tool Registry。

Registry 只负责白名单注册、查找和输出模型可见 Tool Definition，不执行 Tool。
"""

from __future__ import annotations

from agent.models import ModelToolDefinition
from agent.tools.contract import ToolDefinition, ToolPermission

_REGISTRABLE_PERMISSIONS = {
    ToolPermission.READ_ONLY,
    ToolPermission.CONFIRMATION_REQUIRED,
}


class ToolRegistry:
    """按名称管理 ToolDefinition 的内存注册表。

    Registry 只表达“这个工具在白名单里”；是否立即执行由 ApprovalPolicy 和
    ToolExecutor 决定。这样测试和后续确认流程可以注册需确认工具，但不会因此
    获得执行路径。
    """

    def __init__(self, definitions: list[ToolDefinition] | None = None) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        for definition in definitions or []:
            self.register(definition)

    def register(self, definition: ToolDefinition) -> None:
        """注册白名单 ToolDefinition。"""
        if not isinstance(definition, ToolDefinition):
            raise TypeError("ToolRegistry only accepts ToolDefinition")
        name = definition.name.strip()
        if not name:
            raise ValueError("Tool name must not be empty")
        if name in self._definitions:
            raise ValueError(f"Tool already registered: {name}")
        if definition.permission not in _REGISTRABLE_PERMISSIONS:
            raise ValueError(f"Unsupported tool permission: {definition.permission!r}")
        self._definitions[name] = definition

    def get(self, name: str) -> ToolDefinition | None:
        """按名称查找 ToolDefinition；未知名称返回 None。"""
        return self._definitions.get(str(name or "").strip())

    def require(self, name: str) -> ToolDefinition:
        """按名称查找 ToolDefinition；未知名称抛出明确异常。"""
        normalized = str(name or "").strip()
        definition = self.get(normalized)
        if definition is None:
            raise KeyError(f"Unknown tool: {normalized or '<empty>'}")
        return definition

    def list(self) -> tuple[ToolDefinition, ...]:
        """返回已注册 ToolDefinition 的稳定排序快照。"""
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    def to_model_definitions(self) -> tuple[ModelToolDefinition, ...]:
        """输出模型可见工具定义；不包含 handler、权限或内部实现细节。"""
        return tuple(
            ModelToolDefinition(
                name=definition.name,
                description=definition.description,
                input_schema=definition.input_schema,
            )
            for definition in self.list()
        )
