import unittest
from dataclasses import FrozenInstanceError
from typing import Any, Mapping

from agent.runtime.approval_policy import (
    ApprovalPolicy,
    ToolDisposition,
    ToolPolicyReason,
)
from agent.tools.contract import ToolDefinition, ToolPermission


class ApprovalPolicyTest(unittest.TestCase):
    def test_read_only_tool_executes_now(self) -> None:
        decision = ApprovalPolicy().evaluate(_tool_definition())

        self.assertEqual(decision.disposition, ToolDisposition.EXECUTE_NOW)
        self.assertEqual(decision.reason, ToolPolicyReason.READ_ONLY_ALLOWED)

    def test_confirmation_required_tool_requires_confirmation(self) -> None:
        decision = ApprovalPolicy().evaluate(
            _tool_definition(permission=ToolPermission.CONFIRMATION_REQUIRED)
        )

        self.assertEqual(decision.disposition, ToolDisposition.REQUIRE_CONFIRMATION)
        self.assertEqual(decision.reason, ToolPolicyReason.USER_CONFIRMATION_REQUIRED)

    def test_missing_tool_is_denied(self) -> None:
        decision = ApprovalPolicy().evaluate(None)

        self.assertEqual(decision.disposition, ToolDisposition.DENY)
        self.assertEqual(decision.reason, ToolPolicyReason.TOOL_NOT_FOUND)

    def test_unsupported_permission_is_denied(self) -> None:
        definition = _tool_definition()
        object.__setattr__(definition, "permission", "unsupported")

        decision = ApprovalPolicy().evaluate(definition)

        self.assertEqual(decision.disposition, ToolDisposition.DENY)
        self.assertEqual(decision.reason, ToolPolicyReason.UNSUPPORTED_PERMISSION)

    def test_decision_is_immutable(self) -> None:
        decision = ApprovalPolicy().evaluate(_tool_definition())

        with self.assertRaises(FrozenInstanceError):
            decision.disposition = ToolDisposition.DENY

    def test_message_does_not_include_tool_arguments(self) -> None:
        decision = ApprovalPolicy().evaluate(
            _tool_definition(permission=ToolPermission.CONFIRMATION_REQUIRED)
        )

        self.assertNotIn("sensitive-health-note", decision.message)
        self.assertNotIn("arguments", decision.message.lower())

    def test_same_input_returns_same_semantic_decision(self) -> None:
        policy = ApprovalPolicy()
        definition = _tool_definition(permission=ToolPermission.CONFIRMATION_REQUIRED)

        first = policy.evaluate(definition)
        second = policy.evaluate(definition)

        self.assertEqual(first.disposition, second.disposition)
        self.assertEqual(first.reason, second.reason)
        self.assertEqual(first.message, second.message)

    def test_policy_does_not_call_handler_or_validator(self) -> None:
        called = {"handler": 0, "validator": 0}

        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            called["handler"] += 1
            return {"value": 1}

        def validator(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            called["validator"] += 1
            return arguments

        definition = _tool_definition(
            handler=handler,
            argument_validator=validator,
        )

        ApprovalPolicy().evaluate(definition)

        self.assertEqual(called, {"handler": 0, "validator": 0})

    def test_policy_does_not_modify_tool_definition(self) -> None:
        definition = _tool_definition()

        ApprovalPolicy().evaluate(definition)

        self.assertEqual(definition.permission, ToolPermission.READ_ONLY)
        self.assertEqual(definition.name, "sample_tool")


def _tool_definition(
    *,
    permission: ToolPermission = ToolPermission.READ_ONLY,
    handler=None,
    argument_validator=None,
) -> ToolDefinition:
    return ToolDefinition(
        name="sample_tool",
        description="Sample tool",
        input_schema={"type": "object"},
        permission=permission,
        handler=handler or (lambda arguments: {"value": 1}),
        argument_validator=argument_validator,
    )


if __name__ == "__main__":
    unittest.main()
