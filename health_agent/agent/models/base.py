"""模型 Provider 抽象层。

Skill 只依赖 BaseModelProvider，不关心底层是 Mock、OpenAI-compatible API，
还是未来的本地模型。Provider 返回的是候选草案，不具备业务事实权威。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping


class ProviderConfigurationError(RuntimeError):
    """Provider configuration is missing or invalid."""


class ProviderResponseError(RuntimeError):
    """Provider response could not be used by the agent runtime."""


class BaseModelProvider(ABC):
    """所有模型 Provider 的最小接口。"""

    provider_name = "base"

    @abstractmethod
    def generate_initial_planning(
        self,
        prompt: str,
        planning_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """返回 JSON-like INITIAL_PLANNING 草案。

        实现方必须返回对象结构，不能直接声明事实已保存、计划已发布或用户已确认。
        """
