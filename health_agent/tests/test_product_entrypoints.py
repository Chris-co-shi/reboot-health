import io
import json
import unittest
from datetime import datetime, timedelta, timezone

from agent import main as agent_main
from agent.models import ModelResponse, ModelToolCall, ProviderConfigurationError, ProviderResponseError
from agent.runtime.generic_loop import GenericAgentLoop, GenericLoopLimits
from agent.tools.builtin.convert_weight import (
    CONVERT_WEIGHT_UNIT_TOOL_NAME,
    create_convert_weight_unit_tool,
)
from agent.tools.registry import ToolRegistry
from scripts import agent_console
from tests.support.scripted_model_provider import ScriptedModelProvider


class AgentMainEntrypointTest(unittest.TestCase):
    def test_main_success_uses_generic_loop_and_prints_safe_summary(self) -> None:
        loop, provider = _tool_loop()
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = agent_main.main(
            [],
            loop_factory=lambda: loop,
            stdout=stdout,
            stderr=stderr,
        )

        payload = json.loads(stdout.getvalue())
        serialized = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["modelTurns"], 2)
        self.assertEqual(payload["toolCalls"], 1)
        self.assertEqual(payload["answer"], "190 斤是 95 公斤。")
        self.assertNotIn("programDraft", serialized)
        self.assertNotIn("weeklyPlanDraft", serialized)
        self.assertNotIn("system", serialized)
        self.assertEqual([tool.name for tool in provider.calls[0]["tools"]], [CONVERT_WEIGHT_UNIT_TOOL_NAME])

    def test_main_summary_removes_think_tags_from_public_answer(self) -> None:
        loop = _loop_with_responses(
            [ModelResponse(content="<think>internal</think>\n\n公开答案", finish_reason="stop")]
        )
        stdout = io.StringIO()

        exit_code = agent_main.main([], loop_factory=lambda: loop, stdout=stdout)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["answer"], "公开答案")
        self.assertNotIn("internal", stdout.getvalue())

    def test_main_model_error_returns_non_zero(self) -> None:
        loop = _loop_with_responses(
            [
                ProviderResponseError(
                    "raw provider failure",
                    code="provider_failed",
                    safe_summary="provider failed safely",
                )
            ]
        )
        stdout = io.StringIO()

        exit_code = agent_main.main([], loop_factory=lambda: loop, stdout=stdout)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "model_error")
        self.assertEqual(payload["error"]["code"], "MODEL_ERROR")

    def test_main_invalid_response_returns_non_zero(self) -> None:
        loop = _loop_with_responses([ModelResponse(content=" ")])
        stdout = io.StringIO()

        exit_code = agent_main.main([], loop_factory=lambda: loop, stdout=stdout)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "invalid_response")
        self.assertEqual(payload["error"]["code"], "INVALID_RESPONSE")

    def test_main_limit_reached_returns_non_zero(self) -> None:
        loop = _loop_with_responses(
            [
                ModelResponse(
                    tool_calls=(
                        _convert_call({"value": 190, "fromUnit": "jin", "toUnit": "kg"}),
                    )
                )
            ],
            limits=GenericLoopLimits(max_tool_calls=0),
        )
        stdout = io.StringIO()

        exit_code = agent_main.main([], loop_factory=lambda: loop, stdout=stdout)

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "limit_reached")
        self.assertEqual(payload["error"]["code"], "MAX_TOOL_CALLS_REACHED")

    def test_main_configuration_error_returns_non_zero_without_secret(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = agent_main.main(
            [],
            loop_factory=lambda: (_raise_config_error()),
            stdout=stdout,
            stderr=stderr,
        )

        payload = json.loads(stderr.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "configuration_error")
        self.assertNotIn("sk-test-secret", stderr.getvalue())


class AgentConsoleEntrypointTest(unittest.TestCase):
    def test_console_user_text_runs_generic_loop(self) -> None:
        loop, provider = _tool_loop()
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = agent_console.main(
            ["--user-text", "190 斤是多少公斤？请调用可用的重量转换工具，不要自行心算。"],
            loop_factory=lambda: loop,
            stdout=stdout,
            stderr=stderr,
        )

        payload = json.loads(stdout.getvalue())
        serialized = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["modelTurns"], 2)
        self.assertEqual(payload["toolCalls"], 1)
        self.assertEqual(payload["answer"], "190 斤是 95 公斤。")
        self.assertNotIn("programDraft", serialized)
        self.assertEqual(provider.calls[0]["messages"][1].role, "user")

    def test_console_requires_user_text(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = agent_console.main([], stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("--user-text", stderr.getvalue())

    def test_console_error_returns_non_zero(self) -> None:
        loop = _loop_with_responses([ModelResponse(content=None)])
        stdout = io.StringIO()

        exit_code = agent_console.main(
            ["--user-text", "任务"],
            loop_factory=lambda: loop,
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "invalid_response")

    def test_console_configuration_error_returns_non_zero(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = agent_console.main(
            ["--user-text", "任务"],
            loop_factory=lambda: (_raise_config_error()),
            stdout=stdout,
            stderr=stderr,
        )

        payload = json.loads(stderr.getvalue())
        self.assertEqual(exit_code, 2)
        self.assertEqual(payload["status"], "configuration_error")
        self.assertNotIn("sk-test-secret", stderr.getvalue())


def _tool_loop() -> tuple[GenericAgentLoop, ScriptedModelProvider]:
    provider = ScriptedModelProvider(
        [
            ModelResponse(
                tool_calls=(
                    _convert_call({"value": 190, "fromUnit": "jin", "toUnit": "kg"}),
                ),
                finish_reason="tool_calls",
            ),
            ModelResponse(content="190 斤是 95 公斤。", finish_reason="stop"),
        ]
    )
    return _loop_for_provider(provider), provider


def _loop_with_responses(
    responses,
    limits: GenericLoopLimits | None = None,
) -> GenericAgentLoop:
    return _loop_for_provider(ScriptedModelProvider(responses), limits=limits)


def _loop_for_provider(
    provider: ScriptedModelProvider,
    limits: GenericLoopLimits | None = None,
) -> GenericAgentLoop:
    return GenericAgentLoop(
        provider=provider,
        limits=limits,
        tool_registry=ToolRegistry([create_convert_weight_unit_tool()]),
        now_provider=_fixed_now,
    )


def _convert_call(arguments: dict[str, object]) -> ModelToolCall:
    return ModelToolCall(
        id="call-1",
        name=CONVERT_WEIGHT_UNIT_TOOL_NAME,
        raw_arguments=json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        arguments=arguments,
    )


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=8)))


def _raise_config_error():
    raise ProviderConfigurationError("Missing environment variable: LLM_API_KEY sk-test-secret")


if __name__ == "__main__":
    unittest.main()
