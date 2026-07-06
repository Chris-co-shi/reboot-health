from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping


class ProviderConfigurationError(RuntimeError):
    """Provider configuration is missing or invalid."""


class ProviderResponseError(RuntimeError):
    """Provider response could not be used by the agent runtime."""


class BaseModelProvider(ABC):
    provider_name = "base"

    @abstractmethod
    def generate_initial_planning(
        self,
        prompt: str,
        planning_input: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Return a JSON-like INITIAL_PLANNING draft."""
