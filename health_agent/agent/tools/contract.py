"""Tool Contract 定义。

Tool 是 Agent 访问领域能力的白名单入口。Agent 不允许开放 shell、任意文件系统或
任意 SQL Tool；后续每个 Tool 都必须声明权限、影响等级和确认策略。
"""

from __future__ import annotations

from dataclasses import dataclass
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
class ToolContract:
    """受控 Tool 的最小合同。"""

    name: str
    description: str
    permission: ToolPermission
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    timeout_seconds: float = 10.0
