import unittest

from agent.models import (
    ModelResponse,
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


if __name__ == "__main__":
    unittest.main()
