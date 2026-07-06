"""Tool Contract 定义。

Tool 是 Agent 访问领域能力的白名单入口。Agent 不允许开放 shell、任意文件系统或
任意 SQL Tool；后续每个 Tool 都必须声明权限、影响等级和确认策略。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ToolPermission(StrEnum):
    """Tool 权限等级。"""

    READ = "READ"
    PROPOSE = "PROPOSE"
    LOW_RISK_WRITE = "LOW_RISK_WRITE"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    FORBIDDEN = "FORBIDDEN"


@dataclass(frozen=True)
class ToolCall:
    """一次受控 Tool 调用。"""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Tool 执行结果。"""

    name: str
    status: str
    output: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        """返回可序列化结果。"""
        return {
            "name": self.name,
            "status": self.status,
            "output": self.output,
            "requiresConfirmation": self.requires_confirmation,
        }


ToolHandler = Callable[[ToolCall], ToolResult]


@dataclass(frozen=True)
class ToolDefinition:
    """受控 Tool 的最小定义。"""

    name: str
    description: str
    permission: ToolPermission = ToolPermission.READ
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "none"
    requires_confirmation: bool = False
    timeout_seconds: float = 10.0
    handler: ToolHandler | None = None


ToolContract = ToolDefinition
