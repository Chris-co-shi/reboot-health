"""Model Provider 包公共导出。"""

from agent.models.base import (
    ModelMessage,
    ModelOptions,
    ModelProvider,
    ModelResponse,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
    ProviderConfigurationError,
    ProviderResponseError,
)

__all__ = [
    "ModelMessage",
    "ModelOptions",
    "ModelProvider",
    "ModelResponse",
    "ModelToolCall",
    "ModelToolDefinition",
    "ModelUsage",
    "OpenAICompatibleProvider",
    "ProviderConfigurationError",
    "ProviderResponseError",
]


def __getattr__(name: str):
    """Lazily expose concrete providers without coupling base contracts to config."""
    if name == "OpenAICompatibleProvider":
        from agent.models.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider
    raise AttributeError(name)
