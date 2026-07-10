import unittest
from datetime import datetime, timedelta, timezone

from agent.runtime.pending_action import PendingAction
from agent.runtime.pending_action_store import (
    InMemoryPendingActionStore,
    PendingActionAlreadyExistsError,
    PendingActionNotFoundError,
    PendingActionVersionConflictError,
)


class InMemoryPendingActionStoreTest(unittest.TestCase):
    def test_create_and_get_success(self) -> None:
        store = InMemoryPendingActionStore()
        created = store.create(_pending_action())
        loaded = store.get("action-1")

        self.assertEqual(created.action_id, "action-1")
        self.assertEqual(loaded.action_id, "action-1")
        self.assertIsNot(created, loaded)

    def test_duplicate_create_is_rejected(self) -> None:
        store = InMemoryPendingActionStore()
        store.create(_pending_action())

        with self.assertRaises(PendingActionAlreadyExistsError):
            store.create(_pending_action())

    def test_defensive_copy_is_used(self) -> None:
        store = InMemoryPendingActionStore()
        action = _pending_action(arguments={"nested": {"items": [1]}})
        created = store.create(action)

        with self.assertRaises(TypeError):
            created.arguments["nested"] = {"items": [2]}
        loaded = store.get("action-1")
        self.assertEqual(loaded.arguments["nested"]["items"], (1,))

    def test_save_with_expected_version_succeeds(self) -> None:
        store = InMemoryPendingActionStore()
        created = store.create(_pending_action())

        saved = store.save(created, expected_version=0)

        self.assertEqual(saved.version, 1)
        self.assertEqual(store.get("action-1").version, 1)

    def test_stale_version_is_rejected(self) -> None:
        store = InMemoryPendingActionStore()
        created = store.create(_pending_action())
        first_reader = store.get(created.action_id)
        second_reader = store.get(created.action_id)

        store.save(first_reader, expected_version=0)
        with self.assertRaises(PendingActionVersionConflictError):
            store.save(second_reader, expected_version=0)

    def test_missing_save_is_rejected(self) -> None:
        store = InMemoryPendingActionStore()

        with self.assertRaises(PendingActionNotFoundError):
            store.save(_pending_action(), expected_version=0)

    def test_nested_arguments_cannot_be_mutated_through_original_reference(self) -> None:
        store = InMemoryPendingActionStore()
        arguments = {"nested": {"items": [1]}}
        action = _pending_action(arguments=arguments)
        store.create(action)
        arguments["nested"]["items"].append(2)

        loaded = store.get("action-1")
        self.assertEqual(loaded.arguments["nested"]["items"], (1,))


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
