import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from agent.models import ModelMessage, ModelResponse, ModelToolCall, ProviderResponseError
from agent.runtime.generic_loop import (
    ERROR_INVALID_RESPONSE,
    ERROR_MAX_MODEL_TURNS_REACHED,
    ERROR_MAX_TOOL_CALLS_REACHED,
    ERROR_MODEL_ERROR,
    ERROR_TIMEOUT_REACHED,
    GENERIC_STATUS_COMPLETED,
    GENERIC_STATUS_INVALID_RESPONSE,
    GENERIC_STATUS_LIMIT_REACHED,
    GENERIC_STATUS_MODEL_ERROR,
    AgentRequest,
    GenericAgentLoop,
    GenericLoopLimits,
)
from agent.runtime.result import AgentRunResult
from agent.runtime.trace import TraceRecorder
from agent.tools.builtin.convert_weight import (
    CONVERT_WEIGHT_UNIT_TOOL_NAME,
    create_convert_weight_unit_tool,
)
from agent.tools.contract import ToolDefinition
from agent.tools.executor import ToolExecutor
from agent.tools.registry import ToolRegistry
from tests.support.scripted_model_provider import ScriptedModelProvider


class AgentRequestTest(unittest.TestCase):
    def test_valid_agent_request(self) -> None:
        request = AgentRequest(
            user_text="  你好  ",
            session_id=" session-1 ",
            locale=" zh-CN ",
            metadata={"source": "test"},
        )

        self.assertEqual(request.user_text, "你好")
        self.assertEqual(request.session_id, "session-1")
        self.assertEqual(request.locale, "zh-CN")
        self.assertEqual(request.metadata["source"], "test")

    def test_empty_user_text_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AgentRequest(user_text="   ")

    def test_empty_locale_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AgentRequest(user_text="hello", locale=" ")

    def test_metadata_is_immutable_copy(self) -> None:
        metadata = {"source": "test"}
        request = AgentRequest(user_text="hello", metadata=metadata)
        metadata["source"] = "mutated"

        self.assertEqual(request.metadata["source"], "test")
        with self.assertRaises(TypeError):
            request.metadata["source"] = "changed"


class GenericLoopLimitsTest(unittest.TestCase):
    def test_invalid_limits_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            GenericLoopLimits(max_model_turns=0)
        with self.assertRaises(ValueError):
            GenericLoopLimits(max_tool_calls=-1)
        with self.assertRaises(ValueError):
            GenericLoopLimits(timeout_seconds=0)


class GenericAgentLoopDirectAnswerTest(unittest.TestCase):
    def test_direct_answer_completes_with_one_model_turn(self) -> None:
        provider = ScriptedModelProvider(
            [ModelResponse(content="这是直接回答。", finish_reason="stop")]
        )
        result = _run(provider)

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(result.final_text, "这是直接回答。")
        self.assertEqual(result.model_turns, 1)
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(result.finish_reason, "stop")

    def test_messages_order_and_assistant_message(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="完成", finish_reason="stop")])
        result = _run(provider)

        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant"])
        self.assertIsInstance(result.messages[-1], ModelMessage)
        self.assertEqual(result.messages[-1].content, "完成")
        self.assertEqual(result.messages[-1].tool_calls, ())

    def test_empty_registry_sends_no_tools(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="完成", finish_reason="stop")])

        _run(provider)

        self.assertEqual(provider.calls[0]["tools"], ())

    def test_max_tool_calls_zero_allows_direct_answer(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="完成", finish_reason="stop")])

        result = _run(provider, limits=GenericLoopLimits(max_tool_calls=0))

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(result.tool_calls, 0)

    def test_runtime_environment_uses_fixed_datetime_without_today_field(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="完成", finish_reason="stop")])

        _run(provider)

        system_content = provider.calls[0]["messages"][0].content
        self.assertIn('"currentDate": "2026-01-02"', system_content)
        self.assertIn('"currentDateTime": "2026-01-02T03:04:05+08:00"', system_content)
        self.assertIn('"timezone": "+08:00"', system_content)
        self.assertIn('"locale": "zh-CN"', system_content)
        self.assertNotIn('"today"', system_content)

    def test_result_to_dict_serializes_new_fields_without_full_prompt_or_user_text(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="完成", finish_reason="stop")])
        result = _run(provider, user_text="这是一段用户原文")

        payload = result.to_dict()
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(payload["finalText"], "完成")
        self.assertEqual(payload["modelTurns"], 1)
        self.assertEqual(payload["toolCalls"], 0)
        self.assertEqual(payload["finishReason"], "stop")
        self.assertEqual([item["role"] for item in payload["messages"]], ["system", "user", "assistant"])
        self.assertNotIn("你是一个健康管理辅助 Agent", serialized)
        self.assertNotIn("这是一段用户原文", serialized)

    def test_trace_records_summary_steps(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="完成", finish_reason="stop")])
        result = _run(provider)

        step_names = [step["name"] for step in result.trace.steps]
        self.assertEqual(
            step_names,
            [
                "run_started",
                "context_built",
                "model_turn_started",
                "model_turn_completed",
                "run_finished",
            ],
        )
        self.assertEqual(result.trace.final_outcome, GENERIC_STATUS_COMPLETED)


class GenericAgentLoopToolCallTest(unittest.TestCase):
    def test_single_tool_call_returns_tool_result_then_final_content(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    content=None,
                    tool_calls=(
                        _convert_tool_call(
                            {"value": 190, "fromUnit": "jin", "toUnit": "kg"}
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="190 斤是 95 公斤。", finish_reason="stop"),
            ]
        )

        result = _run(provider, registry=_convert_registry())

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(result.final_text, "190 斤是 95 公斤。")
        self.assertEqual(result.model_turns, 2)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant", "tool", "assistant"])
        self.assertEqual(result.messages[2].tool_calls[0].id, "call-1")
        self.assertEqual(result.messages[3].tool_call_id, "call-1")
        self.assertEqual(result.messages[3].name, CONVERT_WEIGHT_UNIT_TOOL_NAME)
        self.assertEqual(_tool_json(result.messages[3])["data"]["convertedValue"], 95)
        self.assertEqual([message.role for message in provider.calls[1]["messages"]], ["system", "user", "assistant", "tool"])

    def test_multiple_tool_calls_execute_in_order_before_next_model_turn(self) -> None:
        first = _convert_tool_call(
            {"value": 190, "fromUnit": "jin", "toUnit": "kg"},
            id="call-first",
        )
        second = _convert_tool_call(
            {"value": 100, "fromUnit": "lb", "toUnit": "kg"},
            id="call-second",
        )
        provider = ScriptedModelProvider(
            [
                ModelResponse(tool_calls=(first, second), finish_reason="tool_calls"),
                ModelResponse(content="两个结果都已计算。", finish_reason="stop"),
            ]
        )

        result = _run(provider, registry=_convert_registry())

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(result.tool_calls, 2)
        self.assertEqual(
            [message.role for message in result.messages],
            ["system", "user", "assistant", "tool", "tool", "assistant"],
        )
        self.assertEqual([result.messages[3].tool_call_id, result.messages[4].tool_call_id], ["call-first", "call-second"])
        self.assertEqual([message.role for message in provider.calls[1]["messages"]], ["system", "user", "assistant", "tool", "tool"])

    def test_content_and_tool_calls_are_preserved_without_early_completion(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    content="我先使用工具计算。",
                    tool_calls=(
                        _convert_tool_call(
                            {"value": 190, "fromUnit": "jin", "toUnit": "kg"}
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="最终答案是 95 公斤。", finish_reason="stop"),
            ]
        )

        result = _run(provider, registry=_convert_registry())

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(result.final_text, "最终答案是 95 公斤。")
        self.assertEqual(result.messages[2].content, "我先使用工具计算。")
        self.assertEqual(len(result.messages[2].tool_calls), 1)

    def test_provider_receives_model_tool_definitions_on_every_turn(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _convert_tool_call(
                            {"value": 190, "fromUnit": "jin", "toUnit": "kg"}
                        ),
                    )
                ),
                ModelResponse(content="完成", finish_reason="stop"),
            ]
        )

        _run(provider, registry=_convert_registry())

        self.assertEqual(len(provider.calls), 2)
        for call in provider.calls:
            tools = call["tools"]
            self.assertEqual([tool.name for tool in tools], [CONVERT_WEIGHT_UNIT_TOOL_NAME])
            self.assertFalse(hasattr(tools[0], "handler"))
            self.assertFalse(hasattr(tools[0], "argument_validator"))
            self.assertFalse(hasattr(tools[0], "permission"))
            self.assertFalse(hasattr(tools[0], "side_effect"))

    def test_tool_executor_registry_mismatch_is_rejected(self) -> None:
        registry = _convert_registry()
        other_registry = ToolRegistry()
        executor = ToolExecutor(other_registry)

        with self.assertRaises(ValueError):
            GenericAgentLoop(
                provider=ScriptedModelProvider([ModelResponse(content="完成")]),
                tool_registry=registry,
                tool_executor=executor,
            )


class GenericAgentLoopToolErrorTest(unittest.TestCase):
    def test_unknown_tool_error_is_returned_to_model(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _tool_call(
                            id="missing-call",
                            name="missing_tool",
                            arguments={"value": 1},
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="工具不存在，我已说明限制。", finish_reason="stop"),
            ]
        )

        result = _run(provider, registry=_convert_registry())

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertIsNone(result.error)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(result.messages[3].role, "tool")
        self.assertEqual(_tool_json(result.messages[3])["error"]["code"], "unknown_tool")

    def test_invalid_arguments_error_is_returned_to_model(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _convert_tool_call(
                            {"value": "190", "fromUnit": "jin", "toUnit": "kg"}
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="参数格式不合法。", finish_reason="stop"),
            ]
        )

        result = _run(provider, registry=_convert_registry())

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertIsNone(result.error)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(_tool_json(result.messages[3])["error"]["code"], "invalid_arguments")

    def test_tool_execution_failed_error_is_returned_to_model_without_traceback(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _tool_call(
                            id="fail-call",
                            name="failing_tool",
                            arguments={"value": 1},
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="工具执行失败。", finish_reason="stop"),
            ]
        )

        result = _run(provider, registry=_failing_registry())

        content = result.messages[3].content
        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(_tool_json(result.messages[3])["error"]["code"], "tool_execution_failed")
        self.assertNotIn("Traceback", content)
        self.assertNotIn("/Users/", content)

    def test_model_can_correct_unknown_tool_then_finish(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _tool_call(
                            id="missing-call",
                            name="missing_tool",
                            arguments={"value": 1},
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(
                    tool_calls=(
                        _convert_tool_call(
                            {"value": 190, "fromUnit": "jin", "toUnit": "kg"},
                            id="corrected-call",
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="纠正后结果是 95 公斤。", finish_reason="stop"),
            ]
        )

        result = _run(provider, registry=_convert_registry())

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(result.model_turns, 3)
        self.assertEqual(result.tool_calls, 2)
        self.assertEqual(_tool_json(result.messages[3])["error"]["code"], "unknown_tool")
        self.assertEqual(_tool_json(result.messages[5])["data"]["convertedValue"], 95)
        self.assertEqual(
            [message.role for message in result.messages],
            ["system", "user", "assistant", "tool", "assistant", "tool", "assistant"],
        )


class GenericAgentLoopLimitTest(unittest.TestCase):
    def test_max_tool_calls_zero_rejects_batch_without_execution(self) -> None:
        calls = {"count": 0}
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _tool_call(id="count-call", name="count_tool", arguments={"value": 1}),
                    ),
                    finish_reason="tool_calls",
                )
            ]
        )

        result = _run(
            provider,
            registry=_counting_registry(calls),
            limits=GenericLoopLimits(max_tool_calls=0),
        )

        self.assertEqual(result.status, GENERIC_STATUS_LIMIT_REACHED)
        self.assertEqual(result.error.code, ERROR_MAX_TOOL_CALLS_REACHED)
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(calls["count"], 0)
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant"])

    def test_batch_exceeding_remaining_tool_limit_is_rejected_as_a_whole(self) -> None:
        calls = {"count": 0}
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _tool_call(id="count-1", name="count_tool", arguments={"value": 1}),
                        _tool_call(id="count-2", name="count_tool", arguments={"value": 2}),
                    ),
                    finish_reason="tool_calls",
                )
            ]
        )

        result = _run(
            provider,
            registry=_counting_registry(calls),
            limits=GenericLoopLimits(max_tool_calls=1),
        )

        self.assertEqual(result.status, GENERIC_STATUS_LIMIT_REACHED)
        self.assertEqual(result.error.code, ERROR_MAX_TOOL_CALLS_REACHED)
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(calls["count"], 0)
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant"])

    def test_max_model_turns_one_does_not_execute_unreturnable_tool_result(self) -> None:
        calls = {"count": 0}
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _tool_call(id="count-call", name="count_tool", arguments={"value": 1}),
                    ),
                    finish_reason="tool_calls",
                )
            ]
        )

        result = _run(
            provider,
            registry=_counting_registry(calls),
            limits=GenericLoopLimits(max_model_turns=1),
        )

        self.assertEqual(result.status, GENERIC_STATUS_LIMIT_REACHED)
        self.assertEqual(result.error.code, ERROR_MAX_MODEL_TURNS_REACHED)
        self.assertEqual(result.model_turns, 1)
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(calls["count"], 0)
        self.assertEqual(len(provider.calls), 1)

    def test_timeout_before_first_provider_call(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="不会调用")])

        result = _run(
            provider,
            limits=GenericLoopLimits(timeout_seconds=1),
            monotonic_provider=ControlledClock([0, 2]),
        )

        self.assertEqual(result.status, GENERIC_STATUS_LIMIT_REACHED)
        self.assertEqual(result.error.code, ERROR_TIMEOUT_REACHED)
        self.assertEqual(result.model_turns, 0)
        self.assertEqual(len(provider.calls), 0)

    def test_timeout_after_provider_response_keeps_assistant_message(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="太晚了", finish_reason="stop")])

        result = _run(
            provider,
            limits=GenericLoopLimits(timeout_seconds=1),
            monotonic_provider=ControlledClock([0, 0, 2]),
        )

        self.assertEqual(result.status, GENERIC_STATUS_LIMIT_REACHED)
        self.assertEqual(result.error.code, ERROR_TIMEOUT_REACHED)
        self.assertEqual(result.model_turns, 1)
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant"])

    def test_timeout_after_tool_execution_keeps_tool_result(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _convert_tool_call(
                            {"value": 190, "fromUnit": "jin", "toUnit": "kg"}
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="不会调用", finish_reason="stop"),
            ]
        )

        result = _run(
            provider,
            registry=_convert_registry(),
            limits=GenericLoopLimits(timeout_seconds=1),
            monotonic_provider=ControlledClock([0, 0, 0, 0, 0, 2]),
        )

        self.assertEqual(result.status, GENERIC_STATUS_LIMIT_REACHED)
        self.assertEqual(result.error.code, ERROR_TIMEOUT_REACHED)
        self.assertEqual(result.model_turns, 1)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant", "tool"])
        self.assertEqual(len(provider.calls), 1)


class GenericAgentLoopErrorPathTest(unittest.TestCase):
    def test_provider_error_returns_model_error(self) -> None:
        provider = ScriptedModelProvider(
            [
                ProviderResponseError(
                    "raw message",
                    code="provider_failed",
                    safe_summary="provider failed safely",
                )
            ]
        )

        result = _run(provider)

        self.assertEqual(result.status, GENERIC_STATUS_MODEL_ERROR)
        self.assertEqual(result.final_text, None)
        self.assertEqual(result.model_turns, 1)
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(result.error.code, ERROR_MODEL_ERROR)
        self.assertEqual(result.error.message, "provider failed safely")

    def test_provider_error_after_tool_result_preserves_counts_and_messages(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _convert_tool_call(
                            {"value": 190, "fromUnit": "jin", "toUnit": "kg"}
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ProviderResponseError(
                    "raw second turn failure",
                    code="provider_failed",
                    safe_summary="second turn failed safely",
                ),
            ]
        )

        result = _run(provider, registry=_convert_registry())

        self.assertEqual(result.status, GENERIC_STATUS_MODEL_ERROR)
        self.assertEqual(result.error.code, ERROR_MODEL_ERROR)
        self.assertEqual(result.model_turns, 2)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant", "tool"])

    def test_none_content_returns_invalid_response(self) -> None:
        result = _run(ScriptedModelProvider([ModelResponse(content=None, finish_reason="stop")]))

        self.assertEqual(result.status, GENERIC_STATUS_INVALID_RESPONSE)
        self.assertEqual(result.error.code, ERROR_INVALID_RESPONSE)
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant"])

    def test_blank_content_returns_invalid_response(self) -> None:
        result = _run(ScriptedModelProvider([ModelResponse(content="   ", finish_reason="stop")]))

        self.assertEqual(result.status, GENERIC_STATUS_INVALID_RESPONSE)
        self.assertEqual(result.error.code, ERROR_INVALID_RESPONSE)

    def test_empty_content_after_tool_result_returns_invalid_response(self) -> None:
        provider = ScriptedModelProvider(
            [
                ModelResponse(
                    tool_calls=(
                        _convert_tool_call(
                            {"value": 190, "fromUnit": "jin", "toUnit": "kg"}
                        ),
                    ),
                    finish_reason="tool_calls",
                ),
                ModelResponse(content="   ", finish_reason="stop"),
            ]
        )

        result = _run(provider, registry=_convert_registry())

        self.assertEqual(result.status, GENERIC_STATUS_INVALID_RESPONSE)
        self.assertEqual(result.error.code, ERROR_INVALID_RESPONSE)
        self.assertEqual(result.model_turns, 2)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant", "tool", "assistant"])


class GenericAgentLoopIsolationTest(unittest.TestCase):
    def test_generic_loop_does_not_import_legacy_business_components(self) -> None:
        source = _generic_loop_source()

        for forbidden in (
            "InitialPlanning",
            "SkillRegistry",
            "PlanningOutput",
            "PlanningQuality",
            "MemoryCandidate",
            "WeeklyPlan",
            "TodayAction",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


class AgentRunResultCompatibilityTest(unittest.TestCase):
    def test_old_result_fields_still_serialize(self) -> None:
        trace = TraceRecorder().start(
            session_id="session-1",
            trigger_type="INITIAL_PLANNING",
            provider="scripted",
        )
        result = AgentRunResult(
            run_id=trace.run_id,
            session_id=trace.session_id,
            status="completed",
            selected_skill="INITIAL_PLANNING",
            final_outcome="completed",
            output={"ok": True},
            trace=trace,
        )

        payload = result.to_dict()

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["selectedSkill"], "INITIAL_PLANNING")
        self.assertEqual(payload["output"], {"ok": True})
        self.assertIsNone(payload["finalText"])
        self.assertEqual(payload["messages"], [])
        self.assertEqual(payload["modelTurns"], 0)
        self.assertEqual(payload["toolCalls"], 0)
        self.assertIsNone(payload["finishReason"])


class ControlledClock:
    def __init__(self, values: list[float]) -> None:
        self._values = list(values)
        self._last = values[-1] if values else 0.0

    def __call__(self) -> float:
        if self._values:
            self._last = self._values.pop(0)
        return self._last


def _run(
    provider: ScriptedModelProvider,
    user_text: str = "任务",
    registry: ToolRegistry | None = None,
    limits: GenericLoopLimits | None = None,
    monotonic_provider=None,
) -> AgentRunResult:
    return GenericAgentLoop(
        provider=provider,
        limits=limits,
        now_provider=_fixed_now,
        tool_registry=registry,
        monotonic_provider=monotonic_provider,
    ).run(AgentRequest(user_text=user_text, locale="zh-CN"))


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=8)))


def _convert_registry() -> ToolRegistry:
    return ToolRegistry([create_convert_weight_unit_tool()])


def _convert_tool_call(arguments: Mapping[str, Any], id: str = "call-1") -> ModelToolCall:
    return _tool_call(
        id=id,
        name=CONVERT_WEIGHT_UNIT_TOOL_NAME,
        arguments=arguments,
    )


def _tool_call(id: str, name: str, arguments: Mapping[str, Any]) -> ModelToolCall:
    return ModelToolCall(
        id=id,
        name=name,
        raw_arguments=json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        arguments=arguments,
    )


def _tool_json(message: ModelMessage) -> dict[str, Any]:
    return json.loads(message.content or "")


def _counting_registry(calls: dict[str, int]) -> ToolRegistry:
    def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        calls["count"] += 1
        return {"value": arguments["value"]}

    return ToolRegistry(
        [
            ToolDefinition(
                name="count_tool",
                description="Count calls",
                input_schema={"type": "object", "properties": {"value": {"type": "number"}}},
                handler=handler,
            )
        ]
    )


def _failing_registry() -> ToolRegistry:
    def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        raise RuntimeError("Traceback /Users/sxc/private.py")

    return ToolRegistry(
        [
            ToolDefinition(
                name="failing_tool",
                description="Always fail",
                input_schema={"type": "object", "properties": {"value": {"type": "number"}}},
                handler=handler,
            )
        ]
    )


def _generic_loop_source() -> str:
    path = Path(__file__).resolve().parents[1] / "agent" / "runtime" / "generic_loop.py"
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
