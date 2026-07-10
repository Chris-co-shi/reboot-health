import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent.config import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    LLMSettings,
    load_llm_settings_from_env,
    should_run_llm_integration,
)
from agent.models import ProviderConfigurationError
import agent.models.openai_compatible as openai_compatible


class LLMConfigTest(unittest.TestCase):
    def test_loads_settings_from_temporary_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dotenv_path = Path(directory) / ".env"
            dotenv_path.write_text(
                "\n".join(
                    (
                        "LLM_BASE_URL=https://dotenv.example/v1",
                        "LLM_API_KEY=dotenv-secret",
                        "LLM_MODEL=dotenv-model",
                        "LLM_TIMEOUT_SECONDS=45",
                    )
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                settings = load_llm_settings_from_env(dotenv_path=dotenv_path)

        self.assertEqual(settings.base_url, "https://dotenv.example/v1")
        self.assertEqual(settings.api_key, "dotenv-secret")
        self.assertEqual(settings.model, "dotenv-model")
        self.assertEqual(settings.timeout_seconds, 45.0)

    def test_shell_environment_overrides_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dotenv_path = Path(directory) / ".env"
            dotenv_path.write_text(
                "\n".join(
                    (
                        "LLM_BASE_URL=https://dotenv.example/v1",
                        "LLM_API_KEY=dotenv-secret",
                        "LLM_MODEL=dotenv-model",
                        "LLM_TIMEOUT_SECONDS=45",
                    )
                ),
                encoding="utf-8",
            )
            shell_env = {
                "LLM_BASE_URL": "https://shell.example/v1",
                "LLM_API_KEY": "shell-secret",
                "LLM_MODEL": "shell-model",
                "LLM_TIMEOUT_SECONDS": "30",
            }

            with patch.dict(os.environ, shell_env, clear=True):
                settings = load_llm_settings_from_env(dotenv_path=dotenv_path)

        self.assertEqual(settings.base_url, "https://shell.example/v1")
        self.assertEqual(settings.api_key, "shell-secret")
        self.assertEqual(settings.model, "shell-model")
        self.assertEqual(settings.timeout_seconds, 30.0)

    def test_missing_required_variables_fail_with_variable_name(self) -> None:
        required_names = ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")
        for missing_name in required_names:
            with self.subTest(missing_name=missing_name):
                env = _valid_env()
                env.pop(missing_name)

                with self.assertRaises(ProviderConfigurationError) as context:
                    LLMSettings.from_mapping(env)

                self.assertIn(missing_name, str(context.exception))

    def test_timeout_defaults_to_sixty_seconds(self) -> None:
        settings = LLMSettings.from_mapping(_valid_env())

        self.assertEqual(settings.timeout_seconds, DEFAULT_LLM_TIMEOUT_SECONDS)

    def test_non_numeric_timeout_fails(self) -> None:
        env = {**_valid_env(), "LLM_TIMEOUT_SECONDS": "soon"}

        with self.assertRaises(ProviderConfigurationError) as context:
            LLMSettings.from_mapping(env)

        self.assertIn("LLM_TIMEOUT_SECONDS", str(context.exception))
        self.assertNotIn(env["LLM_API_KEY"], str(context.exception))

    def test_zero_or_negative_timeout_fails(self) -> None:
        for value in ("0", "-1"):
            with self.subTest(value=value):
                env = {**_valid_env(), "LLM_TIMEOUT_SECONDS": value}

                with self.assertRaises(ProviderConfigurationError) as context:
                    LLMSettings.from_mapping(env)

                self.assertIn("LLM_TIMEOUT_SECONDS", str(context.exception))

    def test_settings_repr_does_not_include_api_key(self) -> None:
        settings = LLMSettings.from_mapping(_valid_env(api_key="repr-secret"))

        self.assertNotIn("repr-secret", repr(settings))

    def test_provider_does_not_load_dotenv_or_read_environment(self) -> None:
        source = inspect.getsource(openai_compatible)

        self.assertNotIn("load_dotenv", source)
        self.assertNotIn("os.environ", source)
        self.assertNotIn("dotenv", source.lower())

    def test_real_llm_integration_is_skipped_unless_explicitly_enabled(self) -> None:
        env = _valid_env()

        self.assertFalse(should_run_llm_integration(env))
        self.assertFalse(should_run_llm_integration({**env, "RUN_LLM_INTEGRATION": "0"}))
        self.assertTrue(should_run_llm_integration({**env, "RUN_LLM_INTEGRATION": "1"}))
        self.assertTrue(should_run_llm_integration({**env, "RUN_LLM_INTEGRATION": "TRUE"}))
        self.assertTrue(should_run_llm_integration({**env, "RUN_LLM_INTEGRATION": "yes"}))
        self.assertFalse(
            should_run_llm_integration(
                {
                    "RUN_LLM_INTEGRATION": "1",
                    "LLM_BASE_URL": "https://model.example/v1",
                }
            )
        )


def _valid_env(api_key: str = "placeholder-secret") -> dict[str, str]:
    return {
        "LLM_BASE_URL": "https://model.example/v1",
        "LLM_API_KEY": api_key,
        "LLM_MODEL": "test-model",
    }


if __name__ == "__main__":
    unittest.main()
