import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.models import ModelMessage, ModelResponse, ModelToolCall, ProviderResponseError
from agent.runtime.generic_loop import (
    ERROR_INVALID_RESPONSE,
    ERROR_MODEL_ERROR,
    ERROR_TOOL_CALL_LOOP_NOT_IMPLEMENTED,
    GENERIC_STATUS_COMPLETED,
    GENERIC_STATUS_INVALID_RESPONSE,
    GENERIC_STATUS_MODEL_ERROR,
    AgentRequest,
    GenericAgentLoop,
    GenericLoopLimits,
)
from agent.runtime.result import AgentRunResult
from agent.runtime.trace import TraceRecorder
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
        result = GenericAgentLoop(
            provider=provider,
            now_provider=_fixed_now,
        ).run(AgentRequest(user_text="请直接回答。"))

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(result.final_text, "这是直接回答。")
        self.assertEqual(result.model_turns, 1)
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(result.finish_reason, "stop")

    def test_messages_order_and_assistant_message(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="完成", finish_reason="stop")])
        result = GenericAgentLoop(provider=provider, now_provider=_fixed_now).run(
            AgentRequest(user_text="任务")
        )

        self.assertEqual([message.role for message in result.messages], ["system", "user", "assistant"])
        self.assertIsInstance(result.messages[-1], ModelMessage)
        self.assertEqual(result.messages[-1].content, "完成")

    def test_provider_receives_no_tools(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="完成", finish_reason="stop")])

        GenericAgentLoop(provider=provider, now_provider=_fixed_now).run(
            AgentRequest(user_text="任务")
        )

        self.assertEqual(provider.calls[0]["tools"], ())

    def test_runtime_environment_uses_fixed_datetime_without_today_field(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="完成", finish_reason="stop")])

        GenericAgentLoop(provider=provider, now_provider=_fixed_now).run(
            AgentRequest(user_text="任务", locale="zh-CN")
        )

        system_content = provider.calls[0]["messages"][0].content
        self.assertIn('"currentDate": "2026-01-02"', system_content)
        self.assertIn('"currentDateTime": "2026-01-02T03:04:05+08:00"', system_content)
        self.assertIn('"timezone": "+08:00"', system_content)
        self.assertIn('"locale": "zh-CN"', system_content)
        self.assertNotIn('"today"', system_content)

    def test_result_to_dict_serializes_new_fields_without_full_prompt_or_user_text(self) -> None:
        provider = ScriptedModelProvider([ModelResponse(content="完成", finish_reason="stop")])
        result = GenericAgentLoop(provider=provider, now_provider=_fixed_now).run(
            AgentRequest(user_text="这是一段用户原文")
        )

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
        result = GenericAgentLoop(provider=provider, now_provider=_fixed_now).run(
            AgentRequest(user_text="任务")
        )

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

        result = GenericAgentLoop(provider=provider, now_provider=_fixed_now).run(
            AgentRequest(user_text="任务")
        )

        self.assertEqual(result.status, GENERIC_STATUS_MODEL_ERROR)
        self.assertEqual(result.final_text, None)
        self.assertEqual(result.model_turns, 1)
        self.assertEqual(result.tool_calls, 0)
        self.assertEqual(result.error.code, ERROR_MODEL_ERROR)
        self.assertEqual(result.error.message, "provider failed safely")

    def test_none_content_returns_invalid_response(self) -> None:
        result = GenericAgentLoop(
            provider=ScriptedModelProvider([ModelResponse(content=None, finish_reason="stop")]),
            now_provider=_fixed_now,
        ).run(AgentRequest(user_text="任务"))

        self.assertEqual(result.status, GENERIC_STATUS_INVALID_RESPONSE)
        self.assertEqual(result.error.code, ERROR_INVALID_RESPONSE)

    def test_blank_content_returns_invalid_response(self) -> None:
        result = GenericAgentLoop(
            provider=ScriptedModelProvider([ModelResponse(content="   ", finish_reason="stop")]),
            now_provider=_fixed_now,
        ).run(AgentRequest(user_text="任务"))

        self.assertEqual(result.status, GENERIC_STATUS_INVALID_RESPONSE)
        self.assertEqual(result.error.code, ERROR_INVALID_RESPONSE)

    def test_tool_call_returns_temporary_not_implemented_error(self) -> None:
        tool_call = ModelToolCall(
            id="call-1",
            name="convert_weight_unit",
            raw_arguments='{"value":190}',
            arguments={"value": 190},
        )
        result = GenericAgentLoop(
            provider=ScriptedModelProvider(
                [ModelResponse(content=None, tool_calls=(tool_call,), finish_reason="tool_calls")]
            ),
            now_provider=_fixed_now,
        ).run(AgentRequest(user_text="任务"))

        self.assertEqual(result.status, GENERIC_STATUS_INVALID_RESPONSE)
        self.assertEqual(result.error.code, ERROR_TOOL_CALL_LOOP_NOT_IMPLEMENTED)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(result.model_turns, 1)
        self.assertEqual([message.role for message in result.messages], ["system", "user"])

    def test_tool_call_path_does_not_execute_tool_runtime(self) -> None:
        source = _generic_loop_source()

        self.assertNotIn("ToolExecutor", source)
        self.assertNotIn("ToolRegistry", source)


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


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=8)))


def _generic_loop_source() -> str:
    path = Path(__file__).resolve().parents[1] / "agent" / "runtime" / "generic_loop.py"
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
