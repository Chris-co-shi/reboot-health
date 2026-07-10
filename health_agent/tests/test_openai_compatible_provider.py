import json
import unittest

from agent.models import (
    ModelMessage,
    ModelOptions,
    ModelToolCall,
    ModelToolDefinition,
    OpenAICompatibleProvider,
    ProviderResponseError,
)
from agent.config import LLMSettings


class OpenAICompatibleProviderTest(unittest.TestCase):
    def test_plain_assistant_content_converts_to_model_response(self) -> None:
        client = _FakeOpenAIClient(
            {
                "model": "test-model",
                "_request_id": "req-1",
                "choices": [
                    {
                        "message": {"content": "普通文本回复"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 4,
                    "completion_tokens": 3,
                    "total_tokens": 7,
                },
            }
        )
        provider = OpenAICompatibleProvider(settings=_provider_settings(), client=client)

        response = provider.complete_turn(
            messages=(ModelMessage(role="user", content="hello"),),
            options=ModelOptions(temperature=0.0),
        )

        self.assertEqual(response.content, "普通文本回复")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.usage.total_tokens, 7)
        self.assertEqual(response.provider_metadata["requestId"], "req-1")
        self.assertEqual(client.last_request["messages"][0]["content"], "hello")

    def test_plain_system_user_assistant_messages_are_serialized(self) -> None:
        client = _FakeOpenAIClient(
            {
                "choices": [
                    {
                        "message": {"content": "ok"},
                        "finish_reason": "stop",
                    }
                ]
            }
        )
        provider = OpenAICompatibleProvider(settings=_provider_settings(), client=client)

        provider.complete_turn(
            messages=(
                ModelMessage(role="system", content="You are concise."),
                ModelMessage(role="user", content="hello"),
                ModelMessage(role="assistant", content="hi"),
            )
        )

        self.assertEqual(
            client.last_request["messages"],
            [
                {"role": "system", "content": "You are concise."},
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ],
        )

    def test_assistant_single_tool_call_and_tool_result_are_serialized(self) -> None:
        client = _FakeOpenAIClient(
            {
                "choices": [
                    {
                        "message": {"content": "done"},
                        "finish_reason": "stop",
                    }
                ]
            }
        )
        provider = OpenAICompatibleProvider(settings=_provider_settings(), client=client)
        tool_call = ModelToolCall(
            id="call-1",
            name="convert_weight_unit",
            raw_arguments='{"value":190,"fromUnit":"jin","toUnit":"kg"}',
            arguments={"value": 190, "fromUnit": "jin", "toUnit": "kg"},
        )

        provider.complete_turn(
            messages=(
                ModelMessage(role="user", content="190 斤是多少公斤？"),
                ModelMessage(role="assistant", tool_calls=(tool_call,)),
                ModelMessage(
                    role="tool",
                    content='{"value":95,"unit":"kg"}',
                    tool_call_id="call-1",
                ),
            )
        )

        assistant_message = client.last_request["messages"][1]
        self.assertEqual(assistant_message["role"], "assistant")
        self.assertIsNone(assistant_message["content"])
        self.assertEqual(len(assistant_message["tool_calls"]), 1)
        self.assertEqual(assistant_message["tool_calls"][0]["id"], "call-1")
        self.assertEqual(assistant_message["tool_calls"][0]["type"], "function")
        self.assertEqual(
            assistant_message["tool_calls"][0]["function"],
            {
                "name": "convert_weight_unit",
                "arguments": '{"value":190,"fromUnit":"jin","toUnit":"kg"}',
            },
        )
        tool_message = client.last_request["messages"][2]
        self.assertEqual(
            tool_message,
            {
                "role": "tool",
                "content": '{"value":95,"unit":"kg"}',
                "tool_call_id": "call-1",
            },
        )

    def test_assistant_multiple_tool_calls_with_content_are_serialized(self) -> None:
        client = _FakeOpenAIClient(
            {
                "choices": [
                    {
                        "message": {"content": "done"},
                        "finish_reason": "stop",
                    }
                ]
            }
        )
        provider = OpenAICompatibleProvider(settings=_provider_settings(), client=client)
        first_call = ModelToolCall(
            id="call-1",
            name="lookup_a",
            raw_arguments='{"id":"a"}',
            arguments={"id": "a"},
        )
        second_call = ModelToolCall(
            id="call-2",
            name="lookup_b",
            raw_arguments='{"id":"b"}',
            arguments={"id": "b"},
        )

        provider.complete_turn(
            messages=(
                ModelMessage(role="user", content="compare"),
                ModelMessage(
                    role="assistant",
                    content="需要查询两个只读信息。",
                    tool_calls=(first_call, second_call),
                ),
            )
        )

        assistant_message = client.last_request["messages"][1]
        self.assertEqual(assistant_message["role"], "assistant")
        self.assertEqual(assistant_message["content"], "需要查询两个只读信息。")
        self.assertEqual(
            [item["id"] for item in assistant_message["tool_calls"]],
            ["call-1", "call-2"],
        )
        self.assertEqual(
            [item["function"]["name"] for item in assistant_message["tool_calls"]],
            ["lookup_a", "lookup_b"],
        )
        self.assertEqual(
            [item["function"]["arguments"] for item in assistant_message["tool_calls"]],
            ['{"id":"a"}', '{"id":"b"}'],
        )

    def test_tool_call_arguments_are_preserved_and_parsed(self) -> None:
        client = _FakeOpenAIClient(
            {
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "function": {
                                        "name": "lookup_health_fact",
                                        "arguments": '{"factId":"f-1"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        )
        provider = OpenAICompatibleProvider(settings=_provider_settings(), client=client)

        response = provider.complete_turn(
            messages=(ModelMessage(role="user", content="lookup"),),
            tools=(
                ModelToolDefinition(
                    name="lookup_health_fact",
                    description="Lookup a fact",
                    input_schema={
                        "type": "object",
                        "properties": {"factId": {"type": "string"}},
                    },
                ),
            ),
        )

        self.assertEqual(response.finish_reason, "tool_calls")
        self.assertEqual(response.tool_calls[0].id, "call-1")
        self.assertEqual(response.tool_calls[0].name, "lookup_health_fact")
        self.assertEqual(response.tool_calls[0].raw_arguments, '{"factId":"f-1"}')
        self.assertEqual(response.tool_calls[0].arguments["factId"], "f-1")
        self.assertEqual(client.last_request["tools"][0]["type"], "function")

    def test_invalid_tool_arguments_json_fails_clearly(self) -> None:
        client = _FakeOpenAIClient(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "function": {
                                        "name": "lookup",
                                        "arguments": "{bad json",
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        )
        provider = OpenAICompatibleProvider(settings=_provider_settings(), client=client)

        with self.assertRaises(ProviderResponseError) as context:
            provider.complete_turn(messages=(ModelMessage(role="user", content="lookup"),))

        self.assertEqual(context.exception.code, "invalid_tool_arguments")

    def test_debug_logs_do_not_include_api_key_or_full_payload_by_default(self) -> None:
        settings = _provider_settings()
        secret = settings.api_key
        client = _FakeOpenAIClient(
            {
                "choices": [
                    {
                        "message": {"content": "ok"},
                        "finish_reason": "stop",
                    }
                ]
            }
        )
        provider = OpenAICompatibleProvider(
            settings=settings,
            debug_log=True,
            client=client,
        )

        with self.assertLogs("agent.models.openai_compatible", level="INFO") as logs:
            provider.complete_turn(
                messages=(ModelMessage(role="user", content=f"secret {secret}"),)
            )

        serialized = "\n".join(logs.output)
        self.assertNotIn(secret, serialized)
        self.assertIn("provider_request_built", serialized)
        self.assertNotIn("secret ", serialized)


class _FakeOpenAIClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.last_request: dict | None = None
        self.chat = _FakeChat(self)


class _FakeChat:
    def __init__(self, root: _FakeOpenAIClient) -> None:
        self.completions = _FakeCompletions(root)


class _FakeCompletions:
    def __init__(self, root: _FakeOpenAIClient) -> None:
        self.root = root

    def create(self, **kwargs):
        self.root.last_request = json.loads(json.dumps(kwargs, ensure_ascii=False))
        return self.root.response


def _provider_settings() -> LLMSettings:
    return LLMSettings(
        base_url="https://model.example/v1",
        api_key="placeholder-not-a-secret",
        model="test-model",
    )


if __name__ == "__main__":
    unittest.main()
