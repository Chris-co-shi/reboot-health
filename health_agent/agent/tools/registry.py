"""Tool Registry 预留模块。

所有 Tool 必须先注册到这里，Agent Loop 后续只能调用白名单 Tool。
"""

from __future__ import annotations

from agent.tools.contract import ToolContract


class ToolRegistry:
    """按名称管理 ToolContract 的内存注册表。"""

    def __init__(self, contracts: list[ToolContract] | None = None) -> None:
        self._contracts: dict[str, ToolContract] = {}
        for contract in contracts or []:
            self.register(contract)

    def register(self, contract: ToolContract) -> None:
        """注册 ToolContract；名称为空时拒绝。"""
        name = contract.name.strip()
        if not name:
            raise ValueError("Tool name must not be empty")
        self._contracts[name] = contract

    def get(self, name: str) -> ToolContract | None:
        """按名称查找 ToolContract。"""
        return self._contracts.get(name.strip())
