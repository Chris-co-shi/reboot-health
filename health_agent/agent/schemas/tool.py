"""Tool Schema 兼容导出。

产品 Tool 合同统一定义在 agent.tools.contract；本模块不再定义第二套 Tool 请求结构。
"""

from __future__ import annotations

from agent.tools.contract import (
    ToolArgumentError,
    ToolDefinition,
    ToolExecutionResult,
    ToolPermission,
    ToolSideEffect,
)

__all__ = [
    "ToolArgumentError",
    "ToolDefinition",
    "ToolExecutionResult",
    "ToolPermission",
    "ToolSideEffect",
]
