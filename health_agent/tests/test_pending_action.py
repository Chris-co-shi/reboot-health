import math
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

from agent.runtime.pending_action import (
    PendingAction,
    PendingActionStatus,
    PendingActionTransitionError,
    calculate_arguments_hash,
    canonicalize_tool_arguments,
    transition_pending_action,
)


class PendingActionTest(unittest.TestCase):
    def test_valid_pending_action_can_be_created(self) -> None:
        action = _pending_action()

        self.assertEqual(action.status, PendingActionStatus.PENDING)
        self.assertEqual(action.version, 0)
        self.assertTrue(action.arguments_hash)
        self.assertEqual(action.idempotency_key, "pending-action:action-1")

    def test_arguments_are_independent_snapshot(self) -> None:
        arguments = {"value": 190, "nested": {"items": [1]}}
        action = _pending_action(arguments=arguments)
        arguments["nested"]["items"].append(2)

        self.assertEqual(action.arguments["nested"]["items"], (1,))
        with self.assertRaises(TypeError):
            action.arguments["value"] = 200

    def test_arguments_hash_ignores_key_order(self) -> None:
        first = calculate_arguments_hash({"b": 2, "a": {"x": [1, True, None]}})
        second = calculate_arguments_hash({"a": {"x": [1, True, None]}, "b": 2})

        self.assertEqual(first, second)
        self.assertEqual(
            canonicalize_tool_arguments({"b": 2, "a": 1}),
            '{"a":1,"b":2}',
        )

    def test_non_json_argument_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _pending_action(arguments={"value": object()})

    def test_nan_and_infinity_are_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _pending_action(arguments={"value": value})

    def test_invalid_time_is_rejected(self) -> None:
        created_at = _fixed_time()
        with self.assertRaises(ValueError):
            _pending_action(
                created_at=created_at,
                updated_at=created_at,
                expires_at=created_at,
            )
        with self.assertRaises(ValueError):
            _pending_action(created_at=datetime(2026, 1, 2, 3, 4, 5))

    def test_invalid_indexes_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _pending_action(assistant_message_index=-1)
        with self.assertRaises(ValueError):
            _pending_action(tool_call_index=-1)

    def test_empty_identity_fields_are_rejected(self) -> None:
        for field_name in (
            "action_id",
            "session_id",
            "originating_run_id",
            "tool_call_id",
            "tool_name",
        ):
            with self.subTest(field_name=field_name):
                kwargs = {field_name: " "}
                with self.assertRaises(ValueError):
                    _pending_action(**kwargs)

    def test_status_is_frozen(self) -> None:
        action = _pending_action()

        with self.assertRaises(FrozenInstanceError):
            action.status = PendingActionStatus.APPROVED

    def test_valid_status_transitions_succeed(self) -> None:
        now = _fixed_time() + timedelta(seconds=1)
        approved = transition_pending_action(
            _pending_action(),
            PendingActionStatus.APPROVED,
            now=now,
        )
        executing = transition_pending_action(
            approved,
            PendingActionStatus.EXECUTING,
            now=now + timedelta(seconds=1),
        )
        executed = transition_pending_action(
            executing,
            PendingActionStatus.EXECUTED,
            now=now + timedelta(seconds=2),
        )

        self.assertEqual(executed.status, PendingActionStatus.EXECUTED)

    def test_reject_and_expire_transitions_succeed_from_pending(self) -> None:
        action = _pending_action(action_id="action-r")
        rejected = transition_pending_action(
            action,
            PendingActionStatus.REJECTED,
        )
        expired = transition_pending_action(
            _pending_action(action_id="action-e"),
            PendingActionStatus.EXPIRED,
        )

        self.assertEqual(rejected.status, PendingActionStatus.REJECTED)
        self.assertGreaterEqual(rejected.updated_at, action.updated_at)
        self.assertEqual(expired.status, PendingActionStatus.EXPIRED)

    def test_invalid_status_transitions_are_rejected(self) -> None:
        rejected = transition_pending_action(
            _pending_action(),
            PendingActionStatus.REJECTED,
        )

        with self.assertRaises(PendingActionTransitionError):
            transition_pending_action(rejected, PendingActionStatus.APPROVED)

        executing = transition_pending_action(
            transition_pending_action(
                _pending_action(action_id="action-2"),
                PendingActionStatus.APPROVED,
            ),
            PendingActionStatus.EXECUTING,
        )
        failed = transition_pending_action(executing, PendingActionStatus.FAILED)
        with self.assertRaises(PendingActionTransitionError):
            transition_pending_action(failed, PendingActionStatus.EXECUTED)


def _pending_action(**overrides) -> PendingAction:
    created_at = overrides.pop("created_at", _fixed_time())
    updated_at = overrides.pop("updated_at", created_at)
    expires_at = overrides.pop("expires_at", created_at + timedelta(minutes=15))
    data = {
        "action_id": "action-1",
        "session_id": "session-1",
        "originating_run_id": "run-1",
        "tool_call_id": "tool-call-1",
        "tool_name": "record_weight_measurement",
        "arguments": {"value": 95, "unit": "kg"},
        "assistant_message_index": 2,
        "tool_call_index": 1,
        "summary": "Record weight measurement",
        "created_at": created_at,
        "updated_at": updated_at,
        "expires_at": expires_at,
    }
    data.update(overrides)
    return PendingAction(**data)


def _fixed_time() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
