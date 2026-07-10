"""确定性测试专用模型 Provider。"""

from __future__ import annotations

from typing import Any, Sequence

from agent.models import (
    ModelMessage,
    ModelOptions,
    ModelProvider,
    ModelResponse,
    ModelToolDefinition,
    ProviderResponseError,
)


class ScriptedModelProvider(ModelProvider):
    """按预设顺序返回 ModelResponse 的测试替身。"""

    provider_name = "scripted"

    def __init__(self, responses: Sequence[ModelResponse | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def complete_turn(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ModelToolDefinition] = (),
        options: ModelOptions | None = None,
    ) -> ModelResponse:
        self.calls.append(
            {
                "messages": tuple(messages),
                "tools": tuple(tools),
                "options": options,
            }
        )
        if not self._responses:
            raise ProviderResponseError(
                "ScriptedModelProvider has no remaining response",
                code="script_exhausted",
                safe_summary="ScriptedModelProvider has no remaining response",
            )
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
