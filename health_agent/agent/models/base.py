"""通用模型 Provider 合同。

本模块只描述一次模型回合的输入输出，不包含 Program、Phase、WeeklyPlan、
TodayAction 等健康规划概念。业务兼容层需要自行把领域 prompt/input 映射为
ModelMessage，再把 ModelResponse.content 解析成自己的 Schema。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence


class ProviderConfigurationError(RuntimeError):
    """Provider configuration is missing or invalid."""


class ProviderResponseError(RuntimeError):
    """Provider response could not be used by the agent runtime."""

    def __init__(
        self,
        message: str,
        code: str = "provider_response_error",
        safe_summary: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_summary = safe_summary or message


class ModelRole:
    """ModelMessage.role 的最小合法性集合。"""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

    @classmethod
    def all(cls) -> tuple[str, ...]:
        return (cls.SYSTEM, cls.USER, cls.ASSISTANT, cls.TOOL)


@dataclass(frozen=True)
class ModelMessage:
    """一次模型回合中的消息。

    Phase 2A 不变量：
    - role 只能是 system / user / assistant / tool。
    - assistant 消息可同时携带 content 与 tool_calls（content 可空）。
    - tool 消息必须携带非空 tool_call_id。
    - system / user / tool 消息不得携带 tool_calls。
    - user / system 消息不应携带 tool_call_id。
    """

    role: str
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[ModelToolCall, ...] = ()

    def __post_init__(self) -> None:
        role = str(self.role or "").strip()
        if role not in ModelRole.all():
            raise ValueError(
                f"ModelMessage role must be one of {ModelRole.all()}, got {self.role!r}"
            )
        object.__setattr__(self, "role", role)
        tool_calls = tuple(self.tool_calls or ())
        object.__setattr__(self, "tool_calls", tool_calls)
        if tool_calls:
            for index, call in enumerate(tool_calls):
                if not isinstance(call, ModelToolCall):
                    raise ValueError(
                        f"ModelMessage tool_calls[{index}] must be ModelToolCall"
                    )
        if role in (ModelRole.SYSTEM, ModelRole.USER, ModelRole.TOOL) and tool_calls:
            raise ValueError(
                f"role={role} messages must not carry tool_calls"
            )
        if role == ModelRole.TOOL:
            tool_call_id = str(self.tool_call_id or "").strip()
            if not tool_call_id:
                raise ValueError("role=tool messages must carry a non-empty tool_call_id")
            object.__setattr__(self, "tool_call_id", tool_call_id)
        elif self.tool_call_id:
            raise ValueError(
                f"role={role} messages must not carry tool_call_id"
            )


@dataclass(frozen=True)
class ModelToolDefinition:
    """可提供给模型选择的工具定义。"""

    name: str
    description: str
    input_schema: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_schema", freeze_mapping(self.input_schema))


@dataclass(frozen=True)
class ModelToolCall:
    """模型请求执行的一次工具调用。"""

    id: str
    name: str
    raw_arguments: str
    arguments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", freeze_mapping(self.arguments))


@dataclass(frozen=True)
class ModelUsage:
    """模型供应商返回的 token 使用量。"""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ModelOptions:
    """一次模型调用的可选参数。"""

    temperature: float | None = None
    max_tokens: int | None = None
    response_format: str | None = None


@dataclass(frozen=True)
class ModelResponse:
    """一次模型回合的通用响应。"""

    content: str | None = None
    tool_calls: tuple[ModelToolCall, ...] = ()
    finish_reason: str = "unknown"
    usage: ModelUsage | None = None
    provider_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_calls", tuple(self.tool_calls))
        object.__setattr__(
            self,
            "provider_metadata",
            freeze_mapping(self.provider_metadata),
        )


class ModelProvider(Protocol):
    """所有产品模型 Provider 必须实现的通用接口。"""

    provider_name: str

    def complete_turn(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition] = (),
        options: ModelOptions | None = None,
    ) -> ModelResponse:
        """执行一次模型回合。"""
        ...


def freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """递归复制并冻结 Mapping，避免 frozen dataclass 暴露可变 dict。"""
    return MappingProxyType({str(key): _freeze_value(item) for key, item in value.items()})


def mutable_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """把冻结或普通 Mapping 递归转回可序列化 dict。"""
    return {str(key): _mutable_value(item) for key, item in value.items()}


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def _mutable_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return mutable_mapping(value)
    if isinstance(value, tuple):
        return [_mutable_value(item) for item in value]
    return value
