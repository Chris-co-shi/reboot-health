import os
import sys
import unittest

from agent.config import LLM_API_KEY_ENV, LLMSettings, should_run_llm_integration
from agent.models import ModelMessage, ModelOptions, ModelResponse, OpenAICompatibleProvider


def _is_explicit_integration_target() -> bool:
    return any(
        arg in ("tests.integration.test_real_llm_provider", "integration.test_real_llm_provider")
        for arg in sys.argv
    )


def _has_explicit_llm_config() -> bool:
    if not _is_explicit_integration_target():
        return False
    return should_run_llm_integration(load_dotenv_file=True)


@unittest.skipUnless(
    _has_explicit_llm_config(),
    "explicit RUN_LLM_INTEGRATION=1 and LLM environment variables are required",
)
class RealLLMProviderIntegrationTest(unittest.TestCase):
    def test_real_provider_returns_non_empty_plain_text_without_logging_api_key(self) -> None:
        settings = LLMSettings.from_mapping(os.environ)
        provider = OpenAICompatibleProvider(settings=settings, debug_log=True)
        api_key = os.environ[LLM_API_KEY_ENV]

        with self.assertLogs("agent.models.openai_compatible", level="INFO") as logs:
            response = provider.complete_turn(
                messages=(
                    ModelMessage(
                        role="system",
                        content="Reply with a short plain text greeting only.",
                    ),
                    ModelMessage(role="user", content="Say hello."),
                ),
                options=ModelOptions(temperature=0.0),
            )

        self.assertIsInstance(response, ModelResponse)
        self.assertTrue(str(response.content or "").strip() or response.tool_calls)
        self.assertEqual(response.provider_metadata["provider"], "openai-compatible")
        self.assertNotIn(api_key, "\n".join(logs.output))
        self.assertNotIn(api_key, repr(provider))
        self.assertNotIn(api_key, repr(settings))


if __name__ == "__main__":
    unittest.main()
