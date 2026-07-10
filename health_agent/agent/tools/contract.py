"""Tool Runtime 合同。

本模块是产品 Tool 的唯一合同定义。模型只能看到 name、description 和
input_schema；handler、校验器和内部实现细节只供确定性 Tool Runtime 使用。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from agent.models.base import freeze_mapping, mutable_mapping


class ToolPermission(StrEnum):
    """Runtime 对 Tool 执行策略的唯一权威声明。

    `READ_ONLY` 可以由通用 ToolExecutor 自动执行；`CONFIRMATION_REQUIRED`
    只允许进入后续确认流程。本枚举不表达业务风险分级，也不表达发布阶段。
    """

    READ_ONLY = "read_only"
    CONFIRMATION_REQUIRED = "confirmation_required"


class ToolArgumentError(ValueError):
    """Tool arguments 未通过工具专属校验。"""


ToolHandler = Callable[[Mapping[str, Any]], Mapping[str, Any]]
ToolArgumentValidator = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class ToolDefinition:
    """受控 Tool 的产品合同。

    权限、handler 和 validator 都是 Runtime 内部元数据，不会进入模型可见
    Tool Schema。`argument_validator` 必须保持确定性和无副作用，因为后续确认
    流程会先校验参数，再冻结被确认的参数快照。
    """

    name: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    permission: ToolPermission = ToolPermission.READ_ONLY
    timeout_seconds: float = 10.0
    handler: ToolHandler | None = None
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    argument_validator: ToolArgumentValidator | None = None

    def __post_init__(self) -> None:
        name = str(self.name or "").strip()
        if not name:
            raise ValueError("Tool name must not be empty")
        object.__setattr__(self, "name", name)

        description = str(self.description or "").strip()
        if not description:
            raise ValueError("Tool description must not be empty")
        object.__setattr__(self, "description", description)

        if not isinstance(self.input_schema, Mapping):
            raise ValueError("Tool input_schema must be a mapping")
        object.__setattr__(self, "input_schema", freeze_mapping(self.input_schema))

        if not isinstance(self.output_schema, Mapping):
            raise ValueError("Tool output_schema must be a mapping")
        object.__setattr__(self, "output_schema", freeze_mapping(self.output_schema))

        if not isinstance(self.permission, ToolPermission):
            raise ValueError("Tool permission must be a ToolPermission")

        try:
            timeout_seconds = float(self.timeout_seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError("Tool timeout_seconds must be positive") from exc
        if timeout_seconds <= 0:
            raise ValueError("Tool timeout_seconds must be positive")
        object.__setattr__(self, "timeout_seconds", timeout_seconds)

        if not callable(self.handler):
            raise ValueError("Tool handler must be callable")
        if self.argument_validator is not None and not callable(self.argument_validator):
            raise ValueError("Tool argument_validator must be callable")

    def validate_arguments(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """执行工具专属参数校验并返回不可变参数 Mapping。

        这里不判断用户确认状态；参数合法性与执行许可是两个独立边界。
        """
        if self.argument_validator is None:
            return freeze_mapping(arguments)
        validated = self.argument_validator(arguments)
        if not isinstance(validated, Mapping):
            raise ToolArgumentError("Tool argument_validator must return a mapping")
        return freeze_mapping(validated)


@dataclass(frozen=True)
class ToolExecutionResult:
    """一次 Tool 执行后可回送给模型的结构化结果。"""

    tool_call_id: str
    tool_name: str
    success: bool
    content: str
    error_code: str | None = None

    def __post_init__(self) -> None:
        json.loads(self.content)


ToolContract = ToolDefinition


def success_content(data: Mapping[str, Any]) -> str:
    """构造成功 Tool Result JSON。"""
    return json.dumps(
        {"success": True, "data": mutable_mapping(data)},
        ensure_ascii=False,
        sort_keys=True,
    )


def error_content(code: str, message: str) -> str:
    """构造失败 Tool Result JSON。"""
    return json.dumps(
        {
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )
