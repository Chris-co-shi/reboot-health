import json
import unittest

from agent.runtime.confirmation import (
    ConfirmationDecision,
    ConfirmationDecisionType,
    ConfirmationResolutionResult,
    ConfirmationResolutionStatus,
    MAX_CONFIRMATION_REASON_CHARS,
)


class ConfirmationDecisionContractTest(unittest.TestCase):
    def test_valid_decision_is_normalized(self) -> None:
        decision = ConfirmationDecision(
            session_id=" session-1 ",
            action_id=" action-1 ",
            decision=ConfirmationDecisionType.APPROVE,
            reason="  ok  ",
        )

        self.assertEqual(decision.session_id, "session-1")
        self.assertEqual(decision.action_id, "action-1")
        self.assertEqual(decision.reason, "ok")

    def test_empty_session_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ConfirmationDecision(
                session_id=" ",
                action_id="action-1",
                decision=ConfirmationDecisionType.APPROVE,
            )

    def test_empty_action_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ConfirmationDecision(
                session_id="session-1",
                action_id=" ",
                decision=ConfirmationDecisionType.APPROVE,
            )

    def test_plain_string_decision_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ConfirmationDecision(
                session_id="session-1",
                action_id="action-1",
                decision="approve",
            )

    def test_reason_length_is_limited(self) -> None:
        with self.assertRaises(ValueError):
            ConfirmationDecision(
                session_id="session-1",
                action_id="action-1",
                decision=ConfirmationDecisionType.REJECT,
                reason="x" * (MAX_CONFIRMATION_REASON_CHARS + 1),
            )

    def test_approve_decision_has_no_argument_override_field(self) -> None:
        decision = ConfirmationDecision(
            session_id="session-1",
            action_id="action-1",
            decision=ConfirmationDecisionType.APPROVE,
        )

        self.assertFalse(hasattr(decision, "arguments"))
        self.assertFalse(hasattr(decision, "raw_arguments"))


class ConfirmationResolutionResultTest(unittest.TestCase):
    def test_result_serialization_is_safe(self) -> None:
        result = ConfirmationResolutionResult(
            status=ConfirmationResolutionStatus.RESOLVED,
            session_id="session-1",
            action_id="action-1",
            tool_name="record_weight_measurement",
            decision=ConfirmationDecisionType.APPROVE,
            tool_succeeded=True,
            model_turns_used=1,
            tool_calls_used=1,
            next_tool_call_index=1,
            remaining_runtime_seconds=30,
        )

        payload = result.to_dict()
        serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(payload["status"], "confirmation_resolved")
        self.assertNotIn("arguments", serialized)
        self.assertNotIn("argumentsHash", serialized)
        self.assertNotIn("idempotency", serialized)


if __name__ == "__main__":
    unittest.main()
