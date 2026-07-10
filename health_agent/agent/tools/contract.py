"""只读 Tool Runtime 合同。

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
    """Phase 2A Tool 权限。"""

    READ_ONLY = "read_only"
    READ = "read_only"
    WRITE = "write"
    LOW_RISK_WRITE = "low_risk_write"
    CONFIRMATION_REQUIRED = "confirmation_required"
    FORBIDDEN = "forbidden"


class ToolSideEffect(StrEnum):
    """Phase 2A Tool 副作用等级。"""

    NONE = "none"
    WRITE = "write"
    EXTERNAL_IO = "external_io"


class ToolArgumentError(ValueError):
    """Tool arguments 未通过工具专属校验。"""


ToolHandler = Callable[[Mapping[str, Any]], Mapping[str, Any]]
ToolArgumentValidator = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class ToolDefinition:
    """受控 Tool 的产品合同。"""

    name: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    permission: ToolPermission = ToolPermission.READ_ONLY
    side_effect: ToolSideEffect = ToolSideEffect.NONE
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

        try:
            permission = ToolPermission(self.permission)
        except ValueError as exc:
            raise ValueError(f"Unsupported tool permission: {self.permission!r}") from exc
        object.__setattr__(self, "permission", permission)

        try:
            side_effect = ToolSideEffect(self.side_effect)
        except ValueError as exc:
            raise ValueError(f"Unsupported tool side_effect: {self.side_effect!r}") from exc
        object.__setattr__(self, "side_effect", side_effect)

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
        """执行工具专属参数校验并返回不可变参数 Mapping。"""
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
