import json
import math
import unittest
from decimal import Decimal
from typing import Any, Mapping

from agent.models import ModelToolCall, ModelToolDefinition
from agent.models.base import mutable_mapping
from agent.tools.builtin.convert_weight import (
    CONVERT_WEIGHT_UNIT_INPUT_SCHEMA,
    CONVERT_WEIGHT_UNIT_OUTPUT_SCHEMA,
    CONVERT_WEIGHT_UNIT_TOOL_NAME,
    convert_weight_unit,
    create_convert_weight_unit_tool,
    validate_convert_weight_arguments,
)
from agent.tools.contract import ToolArgumentError, ToolDefinition, ToolPermission, ToolSideEffect
from agent.tools.executor import ToolExecutor
from agent.tools.registry import ToolRegistry


class ConvertWeightUnitDefinitionTest(unittest.TestCase):
    def test_tool_definition_has_fixed_identity_and_boundaries(self) -> None:
        definition = create_convert_weight_unit_tool()

        self.assertEqual(definition.name, CONVERT_WEIGHT_UNIT_TOOL_NAME)
        self.assertEqual(definition.permission, ToolPermission.READ_ONLY)
        self.assertEqual(definition.side_effect, ToolSideEffect.NONE)
        self.assertGreater(definition.timeout_seconds, 0)
        self.assertTrue(callable(definition.handler))
        self.assertTrue(callable(definition.argument_validator))

    def test_input_schema_matches_public_contract(self) -> None:
        definition = create_convert_weight_unit_tool()
        schema = definition.input_schema

        self.assertEqual(schema["type"], "object")
        self.assertEqual(set(schema["required"]), {"value", "fromUnit", "toUnit"})
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["value"]["type"], "number")
        self.assertEqual(schema["properties"]["value"]["exclusiveMinimum"], 0)
        self.assertEqual(list(schema["properties"]["fromUnit"]["enum"]), ["kg", "lb", "jin"])
        self.assertEqual(list(schema["properties"]["toUnit"]["enum"]), ["kg", "lb", "jin"])
        self.assertEqual(mutable_mapping(schema), dict(CONVERT_WEIGHT_UNIT_INPUT_SCHEMA))

    def test_output_schema_matches_actual_output_fields(self) -> None:
        definition = create_convert_weight_unit_tool()
        schema = definition.output_schema
        data = convert_weight_unit({"value": 190, "fromUnit": "jin", "toUnit": "kg"})

        self.assertEqual(set(schema["required"]), {"value", "fromUnit", "convertedValue", "toUnit"})
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(data.keys()), set(schema["required"]))
        self.assertEqual(mutable_mapping(schema), dict(CONVERT_WEIGHT_UNIT_OUTPUT_SCHEMA))

    def test_handler_and_validator_are_not_visible_to_model(self) -> None:
        registry = ToolRegistry([create_convert_weight_unit_tool()])

        model_definition = registry.to_model_definitions()[0]

        self.assertIsInstance(model_definition, ModelToolDefinition)
        self.assertEqual(model_definition.name, CONVERT_WEIGHT_UNIT_TOOL_NAME)
        self.assertFalse(hasattr(model_definition, "handler"))
        self.assertFalse(hasattr(model_definition, "argument_validator"))
        self.assertFalse(hasattr(model_definition, "permission"))
        self.assertFalse(hasattr(model_definition, "side_effect"))


class ConvertWeightUnitConversionTest(unittest.TestCase):
    def test_jin_to_kg(self) -> None:
        self.assertEqual(
            convert_weight_unit({"value": 190, "fromUnit": "jin", "toUnit": "kg"}),
            {
                "value": 190,
                "fromUnit": "jin",
                "convertedValue": 95,
                "toUnit": "kg",
            },
        )

    def test_kg_to_lb(self) -> None:
        data = convert_weight_unit({"value": 95, "fromUnit": "kg", "toUnit": "lb"})

        self.assertEqual(data["convertedValue"], 209.439149)

    def test_lb_to_kg(self) -> None:
        data = convert_weight_unit({"value": 100, "fromUnit": "lb", "toUnit": "kg"})

        self.assertEqual(data["convertedValue"], 45.359237)

    def test_kg_to_jin(self) -> None:
        data = convert_weight_unit({"value": 1, "fromUnit": "kg", "toUnit": "jin"})

        self.assertEqual(data["convertedValue"], 2)

    def test_jin_to_lb(self) -> None:
        data = convert_weight_unit({"value": 1, "fromUnit": "jin", "toUnit": "lb"})

        self.assertEqual(data["convertedValue"], 1.102311)

    def test_same_unit_conversions_keep_value(self) -> None:
        for unit in ("kg", "lb", "jin"):
            with self.subTest(unit=unit):
                data = convert_weight_unit({"value": 12.5, "fromUnit": unit, "toUnit": unit})
                self.assertEqual(data["convertedValue"], 12.5)
                self.assertEqual(data["fromUnit"], unit)
                self.assertEqual(data["toUnit"], unit)

    def test_decimal_input(self) -> None:
        data = convert_weight_unit(
            {"value": Decimal("1.25"), "fromUnit": "kg", "toUnit": "lb"}
        )

        self.assertEqual(data["value"], 1.25)
        self.assertEqual(data["convertedValue"], 2.755778)

    def test_output_uses_at_most_six_decimal_places(self) -> None:
        data = convert_weight_unit(
            {"value": Decimal("1.23456789"), "fromUnit": "kg", "toUnit": "lb"}
        )

        converted = data["convertedValue"]
        self.assertIsInstance(converted, float)
        decimals = str(converted).split(".", 1)[1]
        self.assertLessEqual(len(decimals), 6)


class ConvertWeightUnitInvalidArgumentsTest(unittest.TestCase):
    def test_missing_value_fails(self) -> None:
        self._assert_invalid({"fromUnit": "jin", "toUnit": "kg"})

    def test_missing_from_unit_fails(self) -> None:
        self._assert_invalid({"value": 190, "toUnit": "kg"})

    def test_missing_to_unit_fails(self) -> None:
        self._assert_invalid({"value": 190, "fromUnit": "jin"})

    def test_extra_field_fails(self) -> None:
        self._assert_invalid(
            {"value": 190, "fromUnit": "jin", "toUnit": "kg", "sourceUnit": "jin"}
        )

    def test_string_value_fails(self) -> None:
        self._assert_invalid({"value": "190", "fromUnit": "jin", "toUnit": "kg"})

    def test_bool_value_fails(self) -> None:
        self._assert_invalid({"value": True, "fromUnit": "jin", "toUnit": "kg"})

    def test_zero_value_fails(self) -> None:
        self._assert_invalid({"value": 0, "fromUnit": "jin", "toUnit": "kg"})

    def test_negative_value_fails(self) -> None:
        self._assert_invalid({"value": -1, "fromUnit": "jin", "toUnit": "kg"})

    def test_nan_value_fails(self) -> None:
        self._assert_invalid({"value": math.nan, "fromUnit": "jin", "toUnit": "kg"})

    def test_infinity_value_fails(self) -> None:
        self._assert_invalid({"value": math.inf, "fromUnit": "jin", "toUnit": "kg"})

    def test_from_unit_unsupported_fails(self) -> None:
        self._assert_invalid({"value": 1, "fromUnit": "pound", "toUnit": "kg"})

    def test_to_unit_unsupported_fails(self) -> None:
        self._assert_invalid({"value": 1, "fromUnit": "kg", "toUnit": "lbs"})

    def test_unit_case_is_not_corrected(self) -> None:
        self._assert_invalid({"value": 1, "fromUnit": "KG", "toUnit": "lb"})

    def test_chinese_unit_is_not_corrected(self) -> None:
        self._assert_invalid({"value": 1, "fromUnit": "斤", "toUnit": "公斤"})

    def test_unit_whitespace_is_not_trimmed(self) -> None:
        self._assert_invalid({"value": 1, "fromUnit": " kg ", "toUnit": "lb"})

    def _assert_invalid(self, arguments: Mapping[str, Any]) -> None:
        with self.assertRaises(ToolArgumentError):
            validate_convert_weight_arguments(arguments)


class ConvertWeightUnitExecutorIntegrationTest(unittest.TestCase):
    def test_register_and_execute_successfully(self) -> None:
        registry = ToolRegistry([create_convert_weight_unit_tool()])
        result = ToolExecutor(registry).execute(
            ModelToolCall(
                id="call-1",
                name=CONVERT_WEIGHT_UNIT_TOOL_NAME,
                raw_arguments='{"value":190,"fromUnit":"jin","toUnit":"kg"}',
                arguments={"value": 190, "fromUnit": "jin", "toUnit": "kg"},
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(result.tool_call_id, "call-1")
        content = json.loads(result.content)
        self.assertTrue(content["success"])
        self.assertEqual(
            content["data"],
            {
                "value": 190,
                "fromUnit": "jin",
                "convertedValue": 95,
                "toUnit": "kg",
            },
        )

    def test_executor_content_is_valid_json(self) -> None:
        result = ToolExecutor(ToolRegistry([create_convert_weight_unit_tool()])).execute(
            _tool_call({"value": 100, "fromUnit": "lb", "toUnit": "kg"})
        )

        json.loads(result.content)

    def test_invalid_arguments_return_invalid_arguments(self) -> None:
        result = ToolExecutor(ToolRegistry([create_convert_weight_unit_tool()])).execute(
            _tool_call({"value": "190", "fromUnit": "jin", "toUnit": "kg"})
        )

        content = json.loads(result.content)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "invalid_arguments")
        self.assertEqual(content["error"]["code"], "invalid_arguments")

    def test_invalid_arguments_do_not_call_handler(self) -> None:
        called = {"count": 0}

        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            called["count"] += 1
            return convert_weight_unit(arguments)

        base_definition = create_convert_weight_unit_tool()
        definition = ToolDefinition(
            name=base_definition.name,
            description=base_definition.description,
            input_schema=base_definition.input_schema,
            output_schema=base_definition.output_schema,
            permission=base_definition.permission,
            side_effect=base_definition.side_effect,
            timeout_seconds=base_definition.timeout_seconds,
            handler=handler,
            argument_validator=base_definition.argument_validator,
        )

        result = ToolExecutor(ToolRegistry([definition])).execute(
            _tool_call({"value": "190", "fromUnit": "jin", "toUnit": "kg"})
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "invalid_arguments")
        self.assertEqual(called["count"], 0)

    def test_tool_call_id_is_preserved(self) -> None:
        result = ToolExecutor(ToolRegistry([create_convert_weight_unit_tool()])).execute(
            _tool_call({"value": 1, "fromUnit": "kg", "toUnit": "jin"}, id="fixed-id")
        )

        self.assertEqual(result.tool_call_id, "fixed-id")


def _tool_call(arguments: Mapping[str, Any], id: str = "call-1") -> ModelToolCall:
    return ModelToolCall(
        id=id,
        name=CONVERT_WEIGHT_UNIT_TOOL_NAME,
        raw_arguments=json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        arguments=arguments,
    )


if __name__ == "__main__":
    unittest.main()
