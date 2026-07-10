import json
import unittest
from typing import Any, Mapping

from agent.models import ModelToolCall, ModelToolDefinition
from agent.tools.contract import (
    ToolArgumentError,
    ToolDefinition,
    ToolExecutionResult,
    ToolPermission,
    ToolSideEffect,
)
from agent.tools.executor import ToolExecutor
from agent.tools.registry import ToolRegistry


class ToolContractTest(unittest.TestCase):
    def test_valid_read_only_none_tool_definition(self) -> None:
        definition = _tool_definition()

        self.assertEqual(definition.name, "sample_tool")
        self.assertEqual(definition.description, "Sample read-only tool")
        self.assertEqual(definition.permission, ToolPermission.READ_ONLY)
        self.assertEqual(definition.side_effect, ToolSideEffect.NONE)
        self.assertEqual(definition.timeout_seconds, 10.0)

    def test_empty_name_fails(self) -> None:
        with self.assertRaises(ValueError):
            _tool_definition(name="   ")

    def test_empty_description_fails(self) -> None:
        with self.assertRaises(ValueError):
            _tool_definition(description="")

    def test_non_positive_timeout_fails(self) -> None:
        for timeout in (0, -1):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    _tool_definition(timeout_seconds=timeout)

    def test_non_callable_handler_fails(self) -> None:
        with self.assertRaises(ValueError):
            ToolDefinition(
                name="sample_tool",
                description="Sample read-only tool",
                handler=None,
            )

    def test_mapping_fields_are_immutable_copies(self) -> None:
        input_schema = {"type": "object", "properties": {"value": {"type": "number"}}}
        output_schema = {"type": "object"}
        definition = _tool_definition(
            input_schema=input_schema,
            output_schema=output_schema,
        )
        input_schema["type"] = "mutated"
        output_schema["type"] = "mutated"

        self.assertEqual(definition.input_schema["type"], "object")
        self.assertEqual(definition.output_schema["type"], "object")
        with self.assertRaises(TypeError):
            definition.input_schema["type"] = "changed"


class ToolRegistryTest(unittest.TestCase):
    def test_register_and_get_by_name(self) -> None:
        definition = _tool_definition()
        registry = ToolRegistry([definition])

        self.assertIs(registry.get("sample_tool"), definition)

    def test_duplicate_registration_fails(self) -> None:
        definition = _tool_definition()
        registry = ToolRegistry([definition])

        with self.assertRaises(ValueError):
            registry.register(definition)

    def test_unknown_name_has_clear_result_and_exception(self) -> None:
        registry = ToolRegistry()

        self.assertIsNone(registry.get("missing"))
        with self.assertRaises(KeyError):
            registry.require("missing")

    def test_model_definitions_are_stable_and_model_visible_only(self) -> None:
        registry = ToolRegistry(
            [
                _tool_definition(name="z_tool"),
                _tool_definition(name="a_tool"),
            ]
        )

        model_definitions = registry.to_model_definitions()

        self.assertEqual([item.name for item in model_definitions], ["a_tool", "z_tool"])
        self.assertTrue(all(isinstance(item, ModelToolDefinition) for item in model_definitions))
        for item in model_definitions:
            self.assertFalse(hasattr(item, "handler"))
            self.assertFalse(hasattr(item, "permission"))
            self.assertFalse(hasattr(item, "side_effect"))
            self.assertNotIn("handler", repr(item))

    def test_non_read_only_tool_registration_fails(self) -> None:
        definition = _tool_definition(permission=ToolPermission.WRITE)
        registry = ToolRegistry()

        with self.assertRaises(ValueError):
            registry.register(definition)

    def test_side_effect_tool_registration_fails(self) -> None:
        definition = _tool_definition(side_effect=ToolSideEffect.WRITE)
        registry = ToolRegistry()

        with self.assertRaises(ValueError):
            registry.register(definition)


class ToolExecutorTest(unittest.TestCase):
    def test_valid_arguments_call_handler(self) -> None:
        calls: list[Mapping[str, Any]] = []

        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            calls.append(arguments)
            return {"value": arguments["value"]}

        definition = _tool_definition(
            handler=handler,
            argument_validator=lambda arguments: {"value": int(arguments["value"])},
        )
        result = ToolExecutor(ToolRegistry([definition])).execute(
            _tool_call(arguments={"value": "95"})
        )

        self.assertTrue(result.success)
        self.assertEqual(calls[0]["value"], 95)

    def test_success_result_content_is_valid_json(self) -> None:
        result = ToolExecutor(ToolRegistry([_tool_definition()])).execute(_tool_call())

        content = json.loads(result.content)
        self.assertTrue(content["success"])
        self.assertEqual(content["data"], {"value": 95})

    def test_unknown_tool_returns_error_without_execution(self) -> None:
        result = ToolExecutor(ToolRegistry()).execute(_tool_call(name="missing"))

        content = json.loads(result.content)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "unknown_tool")
        self.assertEqual(content["error"]["code"], "unknown_tool")

    def test_invalid_arguments_return_error_and_do_not_call_handler(self) -> None:
        called = {"count": 0}

        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            called["count"] += 1
            return {"value": arguments["value"]}

        def validator(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            raise ToolArgumentError("value must be a number")

        definition = _tool_definition(handler=handler, argument_validator=validator)
        result = ToolExecutor(ToolRegistry([definition])).execute(_tool_call())

        content = json.loads(result.content)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "invalid_arguments")
        self.assertEqual(content["error"]["message"], "value must be a number")
        self.assertEqual(called["count"], 0)

    def test_forbidden_tool_returns_error_and_does_not_call_handler(self) -> None:
        called = {"count": 0}

        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            called["count"] += 1
            return {"value": 1}

        registry = ToolRegistry()
        definition = _tool_definition(
            name="unsafe_tool",
            permission=ToolPermission.WRITE,
            handler=handler,
        )
        registry._definitions[definition.name] = definition

        result = ToolExecutor(registry).execute(_tool_call(name="unsafe_tool"))

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "forbidden_tool")
        self.assertEqual(called["count"], 0)

    def test_handler_exception_returns_tool_execution_failed(self) -> None:
        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            raise RuntimeError("boom")

        result = ToolExecutor(ToolRegistry([_tool_definition(handler=handler)])).execute(
            _tool_call()
        )

        content = json.loads(result.content)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "tool_execution_failed")
        self.assertEqual(content["error"]["message"], "Tool execution failed")

    def test_error_result_hides_traceback_and_local_paths(self) -> None:
        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            raise RuntimeError("Traceback /Users/sxc/private.py")

        result = ToolExecutor(ToolRegistry([_tool_definition(handler=handler)])).execute(
            _tool_call()
        )

        self.assertNotIn("Traceback", result.content)
        self.assertNotIn("/Users/", result.content)

    def test_non_serializable_result_returns_invalid_tool_result(self) -> None:
        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            return {"value": object()}

        result = ToolExecutor(ToolRegistry([_tool_definition(handler=handler)])).execute(
            _tool_call()
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "invalid_tool_result")

    def test_non_mapping_result_returns_invalid_tool_result(self) -> None:
        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            return ["not", "a", "mapping"]  # type: ignore[return-value]

        result = ToolExecutor(ToolRegistry([_tool_definition(handler=handler)])).execute(
            _tool_call()
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "invalid_tool_result")

    def test_tool_call_id_is_preserved(self) -> None:
        result = ToolExecutor(ToolRegistry([_tool_definition()])).execute(
            _tool_call(id="original-call-id")
        )

        self.assertEqual(result.tool_call_id, "original-call-id")

    def test_handler_is_not_retried(self) -> None:
        called = {"count": 0}

        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            called["count"] += 1
            raise RuntimeError("fail once")

        result = ToolExecutor(ToolRegistry([_tool_definition(handler=handler)])).execute(
            _tool_call()
        )

        self.assertFalse(result.success)
        self.assertEqual(called["count"], 1)

    def test_tool_execution_result_requires_json_content(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            ToolExecutionResult(
                tool_call_id="call-1",
                tool_name="sample_tool",
                success=True,
                content="not-json",
            )


def _tool_definition(
    name: str = "sample_tool",
    description: str = "Sample read-only tool",
    input_schema: Mapping[str, Any] | None = None,
    output_schema: Mapping[str, Any] | None = None,
    permission: ToolPermission = ToolPermission.READ_ONLY,
    side_effect: ToolSideEffect = ToolSideEffect.NONE,
    timeout_seconds: float = 10.0,
    handler=None,
    argument_validator=None,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=description,
        input_schema=input_schema
        or {"type": "object", "properties": {"value": {"type": "number"}}},
        output_schema=output_schema or {"type": "object"},
        permission=permission,
        side_effect=side_effect,
        timeout_seconds=timeout_seconds,
        handler=handler or (lambda arguments: {"value": 95}),
        argument_validator=argument_validator,
    )


def _tool_call(
    id: str = "call-1",
    name: str = "sample_tool",
    arguments: Mapping[str, Any] | None = None,
) -> ModelToolCall:
    return ModelToolCall(
        id=id,
        name=name,
        raw_arguments='{"value":95}',
        arguments=arguments or {"value": 95},
    )


if __name__ == "__main__":
    unittest.main()
