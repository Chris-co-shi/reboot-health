import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent.models.base import (
    BaseModelProvider,
    ProviderConfigurationError,
    ProviderResponseError,
)
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

    def test_openai_sdk_client_created_with_base_url(self) -> None:
        captured: dict = {}

        def factory(**kwargs):
            captured.update(kwargs)
            return _FakeOpenAISDKClient(content='{"ok": true}')

        OpenAICompatibleProvider(env=_provider_env(), client_factory=factory)

        self.assertEqual(captured["api_key"], _provider_env()["REBOOT_HEALTH_MODEL_API_KEY"])
        self.assertEqual(captured["base_url"], "https://model.example/v1")
        self.assertEqual(captured["timeout"], 30.0)
        self.assertEqual(captured["max_retries"], 0)

    def test_openai_sdk_chat_completion_content_extracted(self) -> None:
        client = _FakeOpenAISDKClient(
            content=json.dumps(_planning_output(True), ensure_ascii=False)
        )
        provider = OpenAICompatibleProvider(env=_provider_env(), client=client)

        result = provider.generate_initial_planning("prompt", {"userText": "想训练"})

        self.assertEqual(result["schemaVersion"], "health-agent.initial-planning.v0")
        self.assertTrue(result["requiresUserConfirmation"])
        self.assertEqual(client.calls[0]["model"], "test-model")
        self.assertEqual(client.calls[0]["messages"][0]["role"], "system")
        self.assertEqual(client.calls[0]["messages"][1]["role"], "user")

    def test_base_url_rejects_chat_completions_endpoint_or_normalizes_safely(self) -> None:
        env = {
            **_provider_env(),
            "REBOOT_HEALTH_MODEL_BASE_URL": "https://api.minimaxi.com/v1/chat/completions",
        }

        with self.assertRaises(ProviderConfigurationError) as context:
            OpenAICompatibleProvider(env=env, client=_FakeOpenAISDKClient())

        self.assertIn("/chat/completions", str(context.exception))
        self.assertIn("https://api.minimaxi.com/v1", str(context.exception))

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
        provider = OpenAICompatibleProvider(
            env=_provider_env(),
            client=_FakeOpenAISDKClient(content="{bad json}"),
        )

        with self.assertRaises(ProviderResponseError) as context:
            provider.generate_initial_planning("prompt", {"userText": "想训练"})

        self.assertEqual(context.exception.code, "invalid_json")

    def test_sdk_api_error_is_wrapped_without_secret(self) -> None:
        secret = _provider_env()["REBOOT_HEALTH_MODEL_API_KEY"]
        error = _FakeSDKAPIError(f"server failed with {secret}")
        provider = OpenAICompatibleProvider(
            env=_provider_env(),
            client=_FakeOpenAISDKClient(error=error),
        )

        with patch("agent.models.openai_compatible.APIError", _FakeSDKAPIError):
            with self.assertRaises(ProviderResponseError) as context:
                provider.generate_initial_planning("prompt", {"userText": "想训练"})

        self.assertEqual(context.exception.code, "provider_response_error")
        self.assertNotIn(secret, context.exception.safe_summary)
        self.assertIn("OpenAI SDK error", context.exception.safe_summary)

    def test_sdk_timeout_error_is_wrapped_without_secret(self) -> None:
        secret = _provider_env()["REBOOT_HEALTH_MODEL_API_KEY"]
        error = _FakeSDKTimeoutError(f"timeout with {secret}")
        provider = OpenAICompatibleProvider(
            env=_provider_env(),
            client=_FakeOpenAISDKClient(error=error),
        )

        with patch("agent.models.openai_compatible.APITimeoutError", _FakeSDKTimeoutError):
            with self.assertRaises(ProviderResponseError) as context:
                provider.generate_initial_planning("prompt", {"userText": "想训练"})

        self.assertEqual(context.exception.code, "timeout")
        self.assertNotIn(secret, context.exception.safe_summary)
        self.assertIn("timed out", context.exception.safe_summary)

    def test_openai_provider_debug_log_does_not_include_api_key_or_user_text(self) -> None:
        client = _FakeOpenAISDKClient(
            content=json.dumps(_planning_output(True), ensure_ascii=False)
        )
        provider = OpenAICompatibleProvider(
            env=_provider_env(),
            debug_log=True,
            client=client,
        )
        user_text = "这是一段不应进入日志的完整健康输入。"

        with self.assertLogs("agent.models.openai_compatible", level="INFO") as logs:
            provider.generate_initial_planning(
                "system prompt should not be logged",
                {"userText": user_text, "today": "2026-07-07"},
            )

        serialized = "\n".join(logs.output)
        self.assertIn("request_start", serialized)
        self.assertIn("response_read", serialized)
        self.assertIn("response_parsed", serialized)
        self.assertIn("responseFormatPresent", serialized)
        self.assertIn("systemPromptChars", serialized)
        self.assertIn("userContentChars", serialized)
        self.assertIn("payloadBytes", serialized)
        self.assertNotIn(_provider_env()["REBOOT_HEALTH_MODEL_API_KEY"], serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn(user_text, serialized)
        self.assertNotIn("system prompt should not be logged", serialized)

    def test_request_content_log_defaults_to_none(self) -> None:
        client = _FakeOpenAISDKClient(
            content=json.dumps(_planning_output(True), ensure_ascii=False)
        )
        provider = OpenAICompatibleProvider(
            env=_provider_env(),
            debug_log=True,
            client=client,
        )

        with self.assertLogs("agent.models.openai_compatible", level="INFO") as logs:
            provider.generate_initial_planning(
                "default-system-prompt-must-not-log",
                {"userText": "default-user-content-must-not-log"},
            )

        serialized = "\n".join(logs.output)
        self.assertIn("provider_request_built", serialized)
        self.assertIn('"mode": "none"', serialized)
        self.assertNotIn("systemPromptPreview", serialized)
        self.assertNotIn("systemPromptRaw", serialized)
        self.assertNotIn("userContentPreview", serialized)
        self.assertNotIn("userContentRaw", serialized)
        self.assertNotIn("default-system-prompt-must-not-log", serialized)
        self.assertNotIn("default-user-content-must-not-log", serialized)

    def test_request_content_log_preview_is_truncated(self) -> None:
        secret = _provider_env()["REBOOT_HEALTH_MODEL_API_KEY"]
        client = _FakeOpenAISDKClient(
            content=json.dumps(_planning_output(True), ensure_ascii=False)
        )
        env = {
            **_provider_env(),
            "REBOOT_HEALTH_MODEL_LOG_REQUEST": "preview",
        }
        provider = OpenAICompatibleProvider(env=env, debug_log=True, client=client)

        with self.assertLogs("agent.models.openai_compatible", level="INFO") as logs:
            provider.generate_initial_planning(
                f"system-preview-start {secret} " + ("x" * 2100) + " system-after-limit",
                {"userText": "user-preview-start " + ("y" * 2100) + " user-after-limit"},
            )

        serialized = "\n".join(logs.output)
        self.assertIn("provider_request_built", serialized)
        self.assertIn("systemPromptPreview", serialized)
        self.assertIn("userContentPreview", serialized)
        self.assertIn("system-preview-start", serialized)
        self.assertIn("user-preview-start", serialized)
        self.assertNotIn("systemPromptRaw", serialized)
        self.assertNotIn("userContentRaw", serialized)
        self.assertNotIn("system-after-limit", serialized)
        self.assertNotIn("user-after-limit", serialized)
        self.assertNotIn(secret, serialized)

    def test_response_content_log_defaults_to_none(self) -> None:
        client = _FakeOpenAISDKClient(
            content=json.dumps(_planning_output(True), ensure_ascii=False)
        )
        provider = OpenAICompatibleProvider(
            env=_provider_env(),
            debug_log=True,
            client=client,
        )

        with self.assertLogs("agent.models.openai_compatible", level="INFO") as logs:
            provider.generate_initial_planning("prompt", {"userText": "想训练"})

        serialized = "\n".join(logs.output)
        self.assertIn("provider_response_raw", serialized)
        self.assertIn('"mode": "none"', serialized)
        self.assertNotIn("contentPreview", serialized)
        self.assertNotIn("contentRaw", serialized)

    def test_response_content_log_preview_is_truncated(self) -> None:
        secret = _provider_env()["REBOOT_HEALTH_MODEL_API_KEY"]
        output = _planning_output(True)
        output["summary"] = f"preview-marker {secret} " + ("x" * 2100) + " after-limit-marker"
        client = _FakeOpenAISDKClient(content=json.dumps(output, ensure_ascii=False))
        env = {
            **_provider_env(),
            "REBOOT_HEALTH_MODEL_LOG_RESPONSE": "preview",
        }
        provider = OpenAICompatibleProvider(env=env, debug_log=True, client=client)

        with self.assertLogs("agent.models.openai_compatible", level="INFO") as logs:
            provider.generate_initial_planning("prompt", {"userText": "想训练"})

        serialized = "\n".join(logs.output)
        self.assertIn("provider_response_raw", serialized)
        self.assertIn("contentPreview", serialized)
        self.assertIn("preview-marker", serialized)
        self.assertNotIn("contentRaw", serialized)
        self.assertNotIn("after-limit-marker", serialized)
        self.assertNotIn(secret, serialized)

    def test_response_content_log_raw_prints_full_content(self) -> None:
        secret = _provider_env()["REBOOT_HEALTH_MODEL_API_KEY"]
        output = _planning_output(True)
        output["summary"] = f"raw-start {secret} " + ("x" * 2100) + " raw-end"
        client = _FakeOpenAISDKClient(content=json.dumps(output, ensure_ascii=False))
        env = {
            **_provider_env(),
            "REBOOT_HEALTH_MODEL_LOG_RESPONSE": "raw",
        }
        provider = OpenAICompatibleProvider(env=env, debug_log=True, client=client)

        with self.assertLogs("agent.models.openai_compatible", level="INFO") as logs:
            provider.generate_initial_planning("prompt", {"userText": "想训练"})

        serialized = "\n".join(logs.output)
        self.assertIn("provider_response_raw", serialized)
        self.assertIn("contentRaw", serialized)
        self.assertIn("raw-start", serialized)
        self.assertIn("raw-end", serialized)
        self.assertNotIn("contentPreview", serialized)
        self.assertNotIn(secret, serialized)

    def test_provider_json_parsed_logs_field_types(self) -> None:
        client = _FakeOpenAISDKClient(
            content=json.dumps(
                {
                    "schemaVersion": "health-agent.initial-planning.v0",
                    "summary": "待确认草案。",
                    "todayActionDraft": "今天只做低强度记录。",
                    "requiresUserConfirmation": True,
                },
                ensure_ascii=False,
            )
        )
        provider = OpenAICompatibleProvider(
            env=_provider_env(),
            debug_log=True,
            client=client,
        )

        with self.assertLogs("agent.models.openai_compatible", level="INFO") as logs:
            provider.generate_initial_planning("prompt", {"userText": "想训练"})

        serialized = "\n".join(logs.output)
        self.assertIn("provider_json_parsed", serialized)
        self.assertIn("fieldTypes", serialized)
        self.assertIn('"todayActionDraft": "str"', serialized)
        self.assertIn('"requiresUserConfirmation": "bool"', serialized)

    def test_response_format_json_object_is_included_when_configured(self) -> None:
        client = _FakeOpenAISDKClient(
            content=json.dumps(_planning_output(True), ensure_ascii=False)
        )
        env = {
            **_provider_env(),
            "REBOOT_HEALTH_MODEL_RESPONSE_FORMAT": "json_object",
        }
        provider = OpenAICompatibleProvider(env=env, client=client)

        provider.generate_initial_planning("prompt", {"userText": "想训练"})

        self.assertEqual(
            client.calls[0]["response_format"],
            {"type": "json_object"},
        )
        self.assertTrue(provider.last_request_shape["responseFormatPresent"])
        self.assertEqual(provider.last_request_shape["responseFormatMode"], "json_object")

    def test_response_format_none_is_omitted(self) -> None:
        client = _FakeOpenAISDKClient(
            content=json.dumps(_planning_output(True), ensure_ascii=False)
        )
        env = {
            **_provider_env(),
            "REBOOT_HEALTH_MODEL_RESPONSE_FORMAT": "none",
        }
        provider = OpenAICompatibleProvider(env=env, client=client)

        provider.generate_initial_planning("prompt", {"userText": "想训练"})

        self.assertNotIn("response_format", client.calls[0])
        self.assertFalse(provider.last_request_shape["responseFormatPresent"])
        self.assertEqual(provider.last_request_shape["responseFormatMode"], "none")

    def test_provider_ping_builds_minimal_payload(self) -> None:
        client = _FakeOpenAISDKClient(content='{"ok": true}')
        provider = OpenAICompatibleProvider(env=_provider_env(), client=client)

        result = provider.ping()

        body = client.calls[0]
        serialized = json.dumps(body, ensure_ascii=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["responseFormat"], "none")
        self.assertEqual(body["temperature"], 0.0)
        self.assertEqual(len(body["messages"]), 2)
        self.assertNotIn("weeklyPlanDraft", serialized)
        self.assertNotIn("programDraft", serialized)
        self.assertLess(result["payloadBytes"], 500)

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


class _FakeOpenAISDKClient:
    def __init__(
        self,
        content: str | dict | None = None,
        error: Exception | None = None,
    ) -> None:
        self.content = '{"ok": true}' if content is None else content
        self.error = error
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create_completion)
        )

    def _create_completion(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ],
            _request_id="req-test",
        )


class _FakeSDKAPIError(Exception):
    pass


class _FakeSDKTimeoutError(Exception):
    pass


def _provider_env() -> dict[str, str]:
    return {
        "REBOOT_HEALTH_MODEL_BASE_URL": "https://model.example/v1",
        "REBOOT_HEALTH_MODEL_API_KEY": "placeholder-not-a-secret",
        "REBOOT_HEALTH_MODEL_NAME": "test-model",
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
