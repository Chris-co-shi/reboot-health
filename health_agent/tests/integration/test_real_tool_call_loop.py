import json
import os
import sys
import unittest

from agent.bootstrap import create_generic_agent_loop_from_env
from agent.config import should_run_llm_integration
from agent.runtime.generic_loop import AgentRequest, GENERIC_STATUS_COMPLETED
from agent.tools.builtin.convert_weight import CONVERT_WEIGHT_UNIT_TOOL_NAME

REAL_TOOL_CALL_PROMPT = "190 斤是多少公斤？请调用可用的重量转换工具，不要自行心算。"


def _is_explicit_integration_target() -> bool:
    return any(
        arg
        in (
            "tests.integration.test_real_tool_call_loop",
            "integration.test_real_tool_call_loop",
        )
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
class RealToolCallLoopIntegrationTest(unittest.TestCase):
    def test_product_bootstrap_completes_real_convert_weight_tool_call(self) -> None:
        loop = create_generic_agent_loop_from_env()
        result = loop.run(AgentRequest(user_text=REAL_TOOL_CALL_PROMPT))

        assistant_tool_messages = [
            message for message in result.messages
            if message.role == "assistant" and message.tool_calls
        ]
        tool_messages = [message for message in result.messages if message.role == "tool"]
        final_assistant_messages = [
            message for message in result.messages
            if message.role == "assistant" and not message.tool_calls and message.content
        ]

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertIsNone(result.selected_skill)
        self.assertGreaterEqual(result.model_turns, 2)
        self.assertGreaterEqual(result.tool_calls, 1)
        self.assertTrue(
            assistant_tool_messages,
            "model completed without producing a native tool call",
        )
        first_tool_names = [
            tool_call.name for tool_call in assistant_tool_messages[0].tool_calls
        ]
        self.assertIn(CONVERT_WEIGHT_UNIT_TOOL_NAME, first_tool_names)
        self.assertTrue(tool_messages)
        self.assertTrue(final_assistant_messages)
        self.assertEqual(
            [message.role for message in result.messages[:5]],
            ["system", "user", "assistant", "tool", "assistant"],
        )
        self.assertTrue(_has_successful_95kg_tool_result(tool_messages))
        self.assertNotIn(os.environ.get("LLM_API_KEY", ""), repr(result))


def _has_successful_95kg_tool_result(tool_messages) -> bool:
    for message in tool_messages:
        if message.name != CONVERT_WEIGHT_UNIT_TOOL_NAME:
            continue
        try:
            payload = json.loads(message.content or "{}")
        except json.JSONDecodeError:
            continue
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            continue
        if data.get("convertedValue") == 95 and data.get("toUnit") == "kg":
            return True
    return False


if __name__ == "__main__":
    unittest.main()
