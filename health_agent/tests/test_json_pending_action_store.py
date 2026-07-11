import os
import stat
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.runtime.pending_action import (
    PendingAction,
    PendingActionStatus,
    transition_pending_action,
)
from agent.runtime.pending_action_store import (
    PendingActionAlreadyExistsError,
    PendingActionNotFoundError,
    PendingActionVersionConflictError,
)
from agent.runtime.storage import (
    FILE_MODE,
    PRIVATE_DIR_MODE,
    JsonFilePendingActionStore,
    JsonPendingActionStoreDataCorrupted,
    JsonPendingActionStoreIOError,
    JsonPendingActionStoreUnsupportedSchema,
    safe_entity_key,
)
from agent.runtime.storage.atomic_file import atomic_write_text
from agent.runtime.storage.errors import JsonStoreIOError
from agent.runtime.storage.json_codec import dumps_payload, pending_action_to_payload
from agent.tools.contract import error_content, success_content


class JsonFilePendingActionStoreTest(unittest.TestCase):
    """JsonFilePendingActionStore 的 Store Port 合同和 PendingAction 特有校验。"""

    def test_create_and_get_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)

            created = store.create(_pending_action())
            loaded = store.get("action-1")

            self.assertEqual(created.action_id, "action-1")
            self.assertEqual(loaded.arguments_hash, created.arguments_hash)
            self.assertEqual(loaded.arguments["value"], 95)
            self.assertIsNot(created, loaded)

    def test_duplicate_create_and_missing_save_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
            store.create(_pending_action())

            with self.assertRaises(PendingActionAlreadyExistsError):
                store.create(_pending_action())
            with self.assertRaises(PendingActionNotFoundError):
                store.save(_pending_action(action_id="missing"), expected_version=0)

    def test_save_uses_disk_version_and_preserves_created_at(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFilePendingActionStore(directory, now_provider=_later_now)
            created = store.create(_pending_action())
            approved = transition_pending_action(created, PendingActionStatus.APPROVED)
            approved = replace(approved, created_at=created.created_at - timedelta(days=1))

            saved = store.save(approved, expected_version=0)

            self.assertEqual(saved.version, 1)
            self.assertEqual(saved.created_at, created.created_at)
            self.assertEqual(saved.updated_at, _later_now())
            self.assertEqual(store.get("action-1").status, PendingActionStatus.APPROVED)

    def test_stale_version_conflict_does_not_overwrite_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
            created = store.create(_pending_action())
            first = transition_pending_action(store.get(created.action_id), PendingActionStatus.APPROVED)
            second = transition_pending_action(store.get(created.action_id), PendingActionStatus.REJECTED)
            store.save(first, expected_version=0)

            with self.assertRaises(PendingActionVersionConflictError):
                store.save(second, expected_version=0)

            self.assertEqual(store.get("action-1").status, PendingActionStatus.APPROVED)

    def test_defensive_copy_and_input_version_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
            action = _pending_action(version=9, arguments={"nested": {"items": [1]}})
            created = store.create(action)

            self.assertEqual(created.version, 0)
            self.assertEqual(action.version, 9)
            with self.assertRaises(TypeError):
                created.arguments["nested"] = {"items": [2]}

    def test_result_fields_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
            created = store.create(_pending_action(action_id="action-exec"))
            executed = transition_pending_action(created, PendingActionStatus.APPROVED)
            executed = transition_pending_action(executed, PendingActionStatus.EXECUTING)
            executed = transition_pending_action(
                executed,
                PendingActionStatus.EXECUTED,
                result_content=success_content({"ok": True}),
            )

            saved = store.save(executed, expected_version=0)
            loaded = store.get("action-exec")

            self.assertEqual(saved.result_content, success_content({"ok": True}))
            self.assertEqual(loaded.status, PendingActionStatus.EXECUTED)
            self.assertIsNone(loaded.result_error_code)

    def test_path_permissions_and_traversal_safe_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            action_id = "../action/escape"
            store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
            store.create(_pending_action(action_id=action_id))
            json_path = Path(directory) / "pending-actions" / f"{safe_entity_key(action_id)}.json"
            lock_path = Path(directory) / "pending-actions" / f"{safe_entity_key(action_id)}.lock"

            self.assertTrue(json_path.exists())
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(Path(directory).stat().st_mode), PRIVATE_DIR_MODE)
                self.assertEqual(stat.S_IMODE(json_path.stat().st_mode), FILE_MODE)
                self.assertEqual(stat.S_IMODE(lock_path.stat().st_mode), FILE_MODE)

    def test_corruption_schema_id_and_hash_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
            action_path = Path(directory) / "pending-actions" / f"{safe_entity_key('action-1')}.json"

            action_path.write_text("{bad-json", encoding="utf-8")
            with self.assertRaises(JsonPendingActionStoreDataCorrupted):
                store.get("action-1")

            payload = pending_action_to_payload(_pending_action(action_id="other-action"))
            atomic_write_text(action_path, dumps_payload(payload))
            with self.assertRaises(JsonPendingActionStoreDataCorrupted):
                store.get("action-1")

            payload = pending_action_to_payload(_pending_action())
            payload["schema_version"] = 999
            atomic_write_text(action_path, dumps_payload(payload))
            with self.assertRaises(JsonPendingActionStoreUnsupportedSchema):
                store.get("action-1")

            payload = pending_action_to_payload(_pending_action())
            payload["data"]["arguments_hash"] = "0" * 64
            atomic_write_text(action_path, dumps_payload(payload))
            with self.assertRaises(JsonPendingActionStoreDataCorrupted):
                store.get("action-1")

    def test_list_all_rejects_file_key_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
            action_path = Path(directory) / "pending-actions" / f"{safe_entity_key('action-1')}.json"
            payload = pending_action_to_payload(_pending_action(action_id="other-action"))
            atomic_write_text(action_path, dumps_payload(payload))

            with self.assertRaises(JsonPendingActionStoreDataCorrupted):
                store.list_all()

    def test_atomic_write_failure_preserves_old_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
            created = store.create(_pending_action())
            approved = transition_pending_action(created, PendingActionStatus.APPROVED)
            failing_store = JsonFilePendingActionStore(
                directory,
                now_provider=_later_now,
                atomic_writer=_failing_writer,
            )

            with self.assertRaises(JsonPendingActionStoreIOError):
                failing_store.save(approved, expected_version=0)

            self.assertEqual(store.get("action-1").version, 0)
            self.assertEqual(store.get("action-1").status, PendingActionStatus.PENDING)


def _pending_action(
    *,
    action_id: str = "action-1",
    version: int = 0,
    arguments: dict | None = None,
) -> PendingAction:
    created_at = _fixed_now()
    return PendingAction(
        action_id=action_id,
        session_id="session-1",
        originating_run_id="run-1",
        tool_call_id="call-1",
        tool_name="record_weight_measurement",
        arguments=arguments or {"value": 95, "unit": "kg"},
        assistant_message_index=2,
        tool_call_index=0,
        summary="Record weight measurement",
        created_at=created_at,
        updated_at=created_at,
        expires_at=created_at + timedelta(minutes=15),
        version=version,
    )


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _later_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 6, tzinfo=timezone.utc)


def _failing_writer(path: Path, text: str) -> None:
    raise JsonStoreIOError("simulated write failure")


if __name__ == "__main__":
    unittest.main()
