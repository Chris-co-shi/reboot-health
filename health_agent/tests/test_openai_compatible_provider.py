import json
import socket
import unittest
import urllib.error
from unittest.mock import patch

from agent.models.base import BaseModelProvider, ProviderConfigurationError, ProviderResponseError
from agent.models.openai_compatible import (
    OpenAICompatibleProvider,
    extract_json_object,
)
from agent.runtime.core import AgentCore
from agent.runtime.result import AgentRunResult
from scripts.smoke_initial_planning import _redacted_summary


class OpenAICompatibleProviderTest(unittest.TestCase):
    def test_openai_provider_missing_config_returns_clear_error(self) -> None:
        with self.assertRaises(ProviderConfigurationError) as context:
            OpenAICompatibleProvider(env={})

        self.assertIn("REBOOT_HEALTH_MODEL_BASE_URL", str(context.exception))

    def test_json_code_block_can_be_extracted(self) -> None:
        result = extract_json_object(
            '说明文字\n```json\n{"outer": {"inner": 1}, "ok": true}\n```\n后续说明'
        )

        self.assertEqual(result["outer"]["inner"], 1)
        self.assertTrue(result["ok"])

    def test_plain_json_can_be_parsed(self) -> None:
        result = extract_json_object('{"schemaVersion": "x", "requiresUserConfirmation": true}')

        self.assertEqual(result["schemaVersion"], "x")
        self.assertTrue(result["requiresUserConfirmation"])

    def test_invalid_json_raises_provider_response_error(self) -> None:
        provider = OpenAICompatibleProvider(env=_provider_env())

        with patch("urllib.request.urlopen", return_value=_FakeResponse(_chat_response("{bad json}"))):
            with self.assertRaises(ProviderResponseError) as context:
                provider.generate_initial_planning("prompt", {"userText": "想训练"})

        self.assertEqual(context.exception.code, "invalid_json")

    def test_openai_provider_timeout_raises_provider_response_error(self) -> None:
        provider = OpenAICompatibleProvider(env=_provider_env())

        with patch("urllib.request.urlopen", return_value=_TimeoutResponse()):
            with self.assertRaises(ProviderResponseError) as context:
                provider.generate_initial_planning("prompt", {"userText": "想训练"})

        self.assertEqual(context.exception.code, "timeout")
        self.assertIn("timed out", context.exception.safe_summary)

    def test_openai_provider_url_error_is_structured(self) -> None:
        provider = OpenAICompatibleProvider(env=_provider_env())

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("network down"),
        ):
            with self.assertRaises(ProviderResponseError) as context:
                provider.generate_initial_planning("prompt", {"userText": "想训练"})

        self.assertEqual(context.exception.code, "provider_response_error")
        self.assertIn("request failed", context.exception.safe_summary)

    def test_openai_provider_url_timeout_is_structured(self) -> None:
        provider = OpenAICompatibleProvider(env=_provider_env())

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError(socket.timeout("read timed out")),
        ):
            with self.assertRaises(ProviderResponseError) as context:
                provider.generate_initial_planning("prompt", {"userText": "想训练"})

        self.assertEqual(context.exception.code, "timeout")

    def test_requires_user_confirmation_false_is_forced_safe(self) -> None:
        result = AgentCore.default(
            provider=_FakeOpenAIProvider(_planning_output(requires_confirmation=False))
        ).run_detailed("INITIAL_PLANNING", {"userText": "想训练"})

        self.assertTrue(result.output["requiresUserConfirmation"])
        self.assertEqual(result.final_outcome, "waiting_confirmation")

    def test_agent_core_run_detailed_with_fake_openai_provider_returns_agent_run_result(self) -> None:
        result = AgentCore.default(
            provider=_FakeOpenAIProvider(_planning_output(requires_confirmation=True))
        ).run_detailed("INITIAL_PLANNING", {"userText": "想低强度恢复训练"})

        self.assertIsInstance(result, AgentRunResult)
        self.assertEqual(result.trace.provider, "openai-compatible")
        self.assertEqual(result.selected_skill, "INITIAL_PLANNING")
        self.assertEqual(result.output["schemaVersion"], "health-agent.initial-planning.v0")

    def test_agent_loop_provider_timeout_returns_failed_agent_run_result(self) -> None:
        result = AgentCore.default(provider=_TimeoutProvider()).run_detailed(
            "INITIAL_PLANNING",
            {"userText": "想低强度恢复训练"},
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.final_outcome, "failed")
        self.assertEqual(result.error.code, "timeout")
        self.assertEqual(result.output["status"], "failed")
        self.assertEqual(result.output["error"]["code"], "timeout")
        self.assertIn("timed out", " ".join(result.warnings))

    def test_smoke_summary_does_not_include_api_key(self) -> None:
        secret_like = "placeholder-not-a-secret"
        summary = _redacted_summary(
            {
                "schemaVersion": "health-agent.run.v0",
                "runId": "run-test",
                "sessionId": "session-test",
                "status": "failed",
                "selectedSkill": "INITIAL_PLANNING",
                "finalOutcome": "failed",
                "trace": {"provider": "openai-compatible"},
                "output": {},
                "memoryCandidates": [],
                "warnings": ["OpenAI-compatible provider request timed out"],
                "error": {
                    "code": "timeout",
                    "message": f"Request failed with Bearer {secret_like}",
                },
            }
        )

        serialized = json.dumps(summary)
        self.assertNotIn(secret_like, serialized)
        self.assertIn("<redacted>", serialized)


class _FakeOpenAIProvider(BaseModelProvider):
    provider_name = "openai-compatible"

    def __init__(self, output: dict) -> None:
        self.output = output

    def generate_initial_planning(self, prompt, planning_input):
        return self.output


class _TimeoutProvider(BaseModelProvider):
    provider_name = "openai-compatible"

    def generate_initial_planning(self, prompt, planning_input):
        raise ProviderResponseError(
            "OpenAI-compatible provider request timed out",
            code="timeout",
            safe_summary="OpenAI-compatible provider request timed out",
        )


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.body).encode("utf-8")


class _TimeoutResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        raise TimeoutError("The read operation timed out")


def _provider_env() -> dict[str, str]:
    return {
        "REBOOT_HEALTH_MODEL_BASE_URL": "https://model.example/v1",
        "REBOOT_HEALTH_MODEL_API_KEY": "placeholder-not-a-secret",
        "REBOOT_HEALTH_MODEL_NAME": "test-model",
    }


def _chat_response(content: str) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                }
            }
        ]
    }


def _planning_output(requires_confirmation: bool) -> dict:
    return {
        "schemaVersion": "health-agent.initial-planning.v0",
        "summary": "生成待确认草案。",
        "understandingCandidates": [{"type": "status", "text": "想训练"}],
        "healthConstraintCandidates": [{"name": "低强度起步"}],
        "goalCandidates": [{"name": "恢复规律训练"}],
        "programDraft": {"status": "draft_requires_confirmation"},
        "phaseDraft": {"status": "draft_requires_confirmation"},
        "weeklyPlanDraft": {"status": "draft_requires_confirmation", "days": []},
        "todayActionDraft": {"status": "draft_requires_confirmation", "actions": []},
        "safetyNotes": ["需要确认后执行。"],
        "questions": [],
        "requiresUserConfirmation": requires_confirmation,
    }


if __name__ == "__main__":
    unittest.main()
