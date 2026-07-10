"""LLM configuration loading for the product Bootstrap."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from agent.models.base import ProviderConfigurationError


LLM_BASE_URL_ENV = "LLM_BASE_URL"
LLM_API_KEY_ENV = "LLM_API_KEY"
LLM_MODEL_ENV = "LLM_MODEL"
LLM_TIMEOUT_SECONDS_ENV = "LLM_TIMEOUT_SECONDS"
RUN_LLM_INTEGRATION_ENV = "RUN_LLM_INTEGRATION"
DEFAULT_LLM_TIMEOUT_SECONDS = 60.0
_TRUE_VALUES = {"1", "true", "yes"}


@dataclass(frozen=True)
class LLMSettings:
    """Validated OpenAI-compatible LLM settings."""

    base_url: str
    api_key: str = field(repr=False)
    model: str
    timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        base_url = _required_string(self.base_url, LLM_BASE_URL_ENV).rstrip("/")
        if base_url.endswith("/chat/completions"):
            raise ProviderConfigurationError(
                f"{LLM_BASE_URL_ENV} must be a base URL like "
                "https://api.example.com/v1, not a /chat/completions endpoint"
            )
        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(
            self,
            "api_key",
            _required_string(self.api_key, LLM_API_KEY_ENV),
        )
        object.__setattr__(
            self,
            "model",
            _required_string(self.model, LLM_MODEL_ENV),
        )
        object.__setattr__(
            self,
            "timeout_seconds",
            _positive_timeout(self.timeout_seconds),
        )

    @classmethod
    def from_mapping(cls, source: Mapping[str, str]) -> "LLMSettings":
        """Build settings from a mapping without reading `.env`."""
        return cls(
            base_url=_required_from_mapping(source, LLM_BASE_URL_ENV),
            api_key=_required_from_mapping(source, LLM_API_KEY_ENV),
            model=_required_from_mapping(source, LLM_MODEL_ENV),
            timeout_seconds=_timeout_from_mapping(source),
        )


def default_dotenv_path() -> Path:
    """Return the canonical health_agent/.env path without depending on cwd."""
    return Path(__file__).resolve().parents[1] / ".env"


def load_llm_environment(dotenv_path: Path | None = None) -> None:
    """Load the canonical dotenv file without overriding shell values."""
    load_dotenv(dotenv_path=dotenv_path or default_dotenv_path(), override=False)


def load_llm_settings_from_env(dotenv_path: Path | None = None) -> LLMSettings:
    """Load the canonical dotenv file, then read validated LLM settings."""
    load_llm_environment(dotenv_path=dotenv_path)
    return LLMSettings.from_mapping(os.environ)


def should_run_llm_integration(
    source: Mapping[str, str] | None = None,
    *,
    dotenv_path: Path | None = None,
    load_dotenv_file: bool = False,
) -> bool:
    """Return whether real LLM integration tests are explicitly enabled."""
    if source is None and load_dotenv_file:
        load_llm_environment(dotenv_path=dotenv_path)
    values = os.environ if source is None else source
    enabled = str(values.get(RUN_LLM_INTEGRATION_ENV) or "").strip().lower()
    if enabled not in _TRUE_VALUES:
        return False
    return all(
        str(values.get(name) or "").strip()
        for name in (LLM_BASE_URL_ENV, LLM_API_KEY_ENV, LLM_MODEL_ENV)
    )


def _required_from_mapping(source: Mapping[str, str], name: str) -> str:
    return _required_string(source.get(name), name)


def _required_string(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ProviderConfigurationError(f"Missing environment variable: {name}")
    return text


def _timeout_from_mapping(source: Mapping[str, str]) -> float:
    raw_value = source.get(LLM_TIMEOUT_SECONDS_ENV)
    if raw_value is None or not str(raw_value).strip():
        return DEFAULT_LLM_TIMEOUT_SECONDS
    return _positive_timeout(raw_value)


def _positive_timeout(value: object) -> float:
    if isinstance(value, bool):
        raise ProviderConfigurationError(
            f"{LLM_TIMEOUT_SECONDS_ENV} must be a positive number"
        )
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ProviderConfigurationError(
            f"{LLM_TIMEOUT_SECONDS_ENV} must be a positive number"
        ) from exc
    if timeout <= 0:
        raise ProviderConfigurationError(
            f"{LLM_TIMEOUT_SECONDS_ENV} must be a positive number"
        )
    return timeout
