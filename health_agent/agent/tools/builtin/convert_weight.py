"""重量单位确定性换算 Tool。"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from agent.tools.contract import (
    ToolArgumentError,
    ToolDefinition,
    ToolPermission,
    ToolSideEffect,
)

CONVERT_WEIGHT_UNIT_TOOL_NAME = "convert_weight_unit"
SUPPORTED_WEIGHT_UNITS = ("kg", "lb", "jin")

_TO_KG = {
    "kg": Decimal("1"),
    "lb": Decimal("0.45359237"),
    "jin": Decimal("0.5"),
}
_OUTPUT_QUANT = Decimal("0.000001")
_REQUIRED_ARGUMENTS = frozenset({"value", "fromUnit", "toUnit"})

CONVERT_WEIGHT_UNIT_INPUT_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "value": {
            "type": "number",
            "exclusiveMinimum": 0,
        },
        "fromUnit": {
            "type": "string",
            "enum": list(SUPPORTED_WEIGHT_UNITS),
        },
        "toUnit": {
            "type": "string",
            "enum": list(SUPPORTED_WEIGHT_UNITS),
        },
    },
    "required": ["value", "fromUnit", "toUnit"],
    "additionalProperties": False,
}

CONVERT_WEIGHT_UNIT_OUTPUT_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "value": {"type": "number"},
        "fromUnit": {
            "type": "string",
            "enum": list(SUPPORTED_WEIGHT_UNITS),
        },
        "convertedValue": {"type": "number"},
        "toUnit": {
            "type": "string",
            "enum": list(SUPPORTED_WEIGHT_UNITS),
        },
    },
    "required": ["value", "fromUnit", "convertedValue", "toUnit"],
    "additionalProperties": False,
}


def create_convert_weight_unit_tool() -> ToolDefinition:
    """创建正式只读重量单位换算 ToolDefinition。"""
    return ToolDefinition(
        name=CONVERT_WEIGHT_UNIT_TOOL_NAME,
        description=(
            "Convert a positive weight value between kilograms, pounds, and Chinese jin."
        ),
        input_schema=CONVERT_WEIGHT_UNIT_INPUT_SCHEMA,
        output_schema=CONVERT_WEIGHT_UNIT_OUTPUT_SCHEMA,
        permission=ToolPermission.READ_ONLY,
        side_effect=ToolSideEffect.NONE,
        timeout_seconds=1.0,
        handler=convert_weight_unit,
        argument_validator=validate_convert_weight_arguments,
    )


def validate_convert_weight_arguments(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    """校验 convert_weight_unit 参数并返回规范化参数。"""
    if not isinstance(arguments, Mapping):
        raise ToolArgumentError("arguments must be a JSON object")

    keys = set(arguments.keys())
    missing = sorted(_REQUIRED_ARGUMENTS - keys)
    if missing:
        raise ToolArgumentError(f"missing required argument: {missing[0]}")
    extra = sorted(keys - _REQUIRED_ARGUMENTS)
    if extra:
        raise ToolArgumentError(f"unexpected argument: {extra[0]}")

    value = _parse_positive_decimal(arguments["value"])
    from_unit = _validate_unit(arguments["fromUnit"], "fromUnit")
    to_unit = _validate_unit(arguments["toUnit"], "toUnit")
    return {
        "value": value,
        "fromUnit": from_unit,
        "toUnit": to_unit,
    }


def convert_weight_unit(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    """执行确定性重量单位换算，只返回业务 data。"""
    validated = validate_convert_weight_arguments(arguments)
    value = validated["value"]
    from_unit = validated["fromUnit"]
    to_unit = validated["toUnit"]
    converted_value = value * _TO_KG[from_unit] / _TO_KG[to_unit]
    return {
        "value": _decimal_to_json_number(value),
        "fromUnit": from_unit,
        "convertedValue": _decimal_to_json_number(converted_value),
        "toUnit": to_unit,
    }


def _parse_positive_decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ToolArgumentError("value must be a finite positive number")
    if isinstance(value, int):
        decimal_value = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ToolArgumentError("value must be a finite positive number")
        decimal_value = Decimal(str(value))
    elif isinstance(value, Decimal):
        decimal_value = value
    else:
        raise ToolArgumentError("value must be a finite positive number")

    if not decimal_value.is_finite() or decimal_value <= 0:
        raise ToolArgumentError("value must be a finite positive number")
    return decimal_value


def _validate_unit(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or value not in SUPPORTED_WEIGHT_UNITS:
        raise ToolArgumentError(f"{field_name} must be one of: kg, lb, jin")
    return value


def _decimal_to_json_number(value: Decimal) -> int | float:
    quantized = value.quantize(_OUTPUT_QUANT, rounding=ROUND_HALF_UP)
    if quantized == quantized.to_integral_value():
        return int(quantized)
    return float(quantized.normalize())
