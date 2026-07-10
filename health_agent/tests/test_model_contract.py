import unittest

from agent.models import (
    ModelMessage,
    ModelResponse,
    ModelRole,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
)


class ModelContractTest(unittest.TestCase):
    def test_model_response_supports_plain_text_and_usage(self) -> None:
        response = ModelResponse(
            content="hello",
            finish_reason="stop",
            usage=ModelUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5),
            provider_metadata={"requestId": "req-1"},
        )

        self.assertEqual(response.content, "hello")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.usage.total_tokens, 5)
        self.assertEqual(response.provider_metadata["requestId"], "req-1")

    def test_tool_definition_and_call_expose_immutable_mappings(self) -> None:
        input_schema = {"type": "object", "properties": {"q": {"type": "string"}}}
        definition = ModelToolDefinition(
            name="lookup",
            description="Lookup data",
            input_schema=input_schema,
        )
        input_schema["type"] = "mutated"
        tool_call = ModelToolCall(
            id="call-1",
            name="lookup",
            raw_arguments='{"q":"x"}',
            arguments={"q": "x"},
        )

        self.assertEqual(definition.input_schema["type"], "object")
        self.assertEqual(tool_call.raw_arguments, '{"q":"x"}')
        self.assertEqual(tool_call.arguments["q"], "x")
        with self.assertRaises(TypeError):
            tool_call.arguments["q"] = "changed"

    def test_assistant_message_can_carry_only_content(self) -> None:
        message = ModelMessage(role=ModelRole.ASSISTANT, content="普通文本回复")

        self.assertEqual(message.role, ModelRole.ASSISTANT)
        self.assertEqual(message.content, "普通文本回复")
        self.assertEqual(message.tool_calls, ())

    def test_assistant_message_can_carry_only_tool_calls(self) -> None:
        call = ModelToolCall(
            id="call-1",
            name="lookup",
            raw_arguments='{"q":"x"}',
            arguments={"q": "x"},
        )
        message = ModelMessage(role=ModelRole.ASSISTANT, tool_calls=(call,))

        self.assertEqual(message.role, ModelRole.ASSISTANT)
        self.assertIsNone(message.content)
        self.assertEqual(message.tool_calls, (call,))

    def test_assistant_message_carries_tool_calls_with_content(self) -> None:
        call = ModelToolCall(
            id="call-1",
            name="convert_weight_unit",
            raw_arguments='{"value":190}',
            arguments={"value": 190},
        )
        message = ModelMessage(
            role=ModelRole.ASSISTANT,
            content="先换算",
            tool_calls=(call,),
        )

        self.assertEqual(message.role, ModelRole.ASSISTANT)
        self.assertEqual(message.content, "先换算")
        self.assertEqual(len(message.tool_calls), 1)
        self.assertEqual(message.tool_calls[0].id, "call-1")

    def test_tool_message_requires_tool_call_id(self) -> None:
        result = ModelMessage(
            role=ModelRole.TOOL,
            content='{"value":95}',
            tool_call_id="call-1",
        )
        self.assertEqual(result.role, ModelRole.TOOL)
        self.assertEqual(result.tool_call_id, "call-1")

        with self.assertRaises(ValueError):
            ModelMessage(role=ModelRole.TOOL, content="x")

    def test_system_user_tool_must_not_carry_tool_calls(self) -> None:
        call = ModelToolCall(id="x", name="n", raw_arguments="{}")

        for role in (ModelRole.SYSTEM, ModelRole.USER, ModelRole.TOOL):
            with self.subTest(role=role):
                with self.assertRaises(ValueError):
                    ModelMessage(role=role, content="x", tool_calls=(call,))

    def test_tool_call_id_must_only_appear_on_tool_messages(self) -> None:
        for role in (ModelRole.SYSTEM, ModelRole.USER, ModelRole.ASSISTANT):
            with self.subTest(role=role):
                with self.assertRaises(ValueError):
                    ModelMessage(role=role, content="x", tool_call_id="call-1")

    def test_unknown_role_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ModelMessage(role="planner", content="x")


if __name__ == "__main__":
    unittest.main()
