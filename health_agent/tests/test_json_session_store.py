import os
import stat
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.models import ModelMessage, ModelToolCall
from agent.runtime.continuation import AgentContinuation
from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    SessionAlreadyExistsError,
    SessionNotFoundError,
    SessionVersionConflictError,
)
from agent.runtime.storage import (
    FILE_MODE,
    PRIVATE_DIR_MODE,
    JsonFileSessionStore,
    JsonSessionStoreDataCorrupted,
    JsonSessionStoreIOError,
    JsonSessionStoreUnsupportedSchema,
    safe_entity_key,
    session_to_payload,
)
from agent.runtime.storage.atomic_file import atomic_write_text
from agent.runtime.storage.errors import JsonStoreIOError
from agent.runtime.storage.json_codec import dumps_payload


class JsonFileSessionStoreTest(unittest.TestCase):
    """JsonFileSessionStore 必须与 InMemorySessionStore 保持同一外部合同。"""

    def test_create_and_get_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)

            created = store.create(_session())
            loaded = store.get("session-1")

            self.assertEqual(created.session_id, "session-1")
            self.assertEqual(created.version, 0)
            self.assertEqual(loaded.status, AgentSessionStatus.WAITING_CONFIRMATION)
            self.assertEqual(len(loaded.messages), 3)
            self.assertEqual(loaded.messages[2].tool_calls[0].id, "call-1")
            self.assertEqual(loaded.continuation.next_tool_call_index, 0)
            self.assertIsNot(created, loaded)

    def test_duplicate_create_and_missing_save_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            store.create(_session())

            with self.assertRaises(SessionAlreadyExistsError):
                store.create(_session())
            with self.assertRaises(SessionNotFoundError):
                store.save(_session(session_id="missing"), expected_version=0)

    def test_save_uses_disk_version_and_preserves_created_at(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_later_now)
            created = store.create(_session())
            mutated = replace(created, created_at=created.created_at - timedelta(days=1))
            mutated.context_summary = "saved"

            saved = store.save(mutated, expected_version=0)

            self.assertEqual(saved.version, 1)
            self.assertEqual(saved.created_at, created.created_at)
            self.assertEqual(saved.updated_at, _later_now())
            self.assertEqual(store.get("session-1").context_summary, "saved")

    def test_stale_version_conflict_does_not_overwrite_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            created = store.create(_session())
            first = store.get(created.session_id)
            second = store.get(created.session_id)
            first.context_summary = "first"
            second.context_summary = "second"
            store.save(first, expected_version=0)

            with self.assertRaises(SessionVersionConflictError):
                store.save(second, expected_version=0)

            self.assertEqual(store.get("session-1").context_summary, "first")

    def test_get_returns_defensive_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            store.create(_session())
            loaded = store.get("session-1")
            loaded.messages.append(ModelMessage(role="assistant", content="mutated"))

            self.assertEqual(len(store.get("session-1").messages), 3)

    def test_create_input_object_is_not_mutated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            session = _session(version=9)

            created = store.create(session)

            self.assertEqual(created.version, 0)
            self.assertEqual(session.version, 9)

    def test_path_traversal_id_uses_hashed_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            dangerous_id = "../escape/session"
            store.create(_session(session_id=dangerous_id))
            expected = Path(directory) / "sessions" / f"{safe_entity_key(dangerous_id)}.json"

            self.assertTrue(expected.exists())
            self.assertFalse((Path(directory).parent / "escape").exists())

    def test_file_and_directory_permissions_are_private_on_posix(self) -> None:
        if os.name == "nt":
            self.skipTest("POSIX mode bits are best-effort on Windows")
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            store.create(_session())
            json_path = Path(directory) / "sessions" / f"{safe_entity_key('session-1')}.json"
            lock_path = Path(directory) / "sessions" / f"{safe_entity_key('session-1')}.lock"

            self.assertEqual(stat.S_IMODE(Path(directory).stat().st_mode), PRIVATE_DIR_MODE)
            self.assertEqual(stat.S_IMODE((Path(directory) / "sessions").stat().st_mode), PRIVATE_DIR_MODE)
            self.assertEqual(stat.S_IMODE(json_path.stat().st_mode), FILE_MODE)
            self.assertEqual(stat.S_IMODE(lock_path.stat().st_mode), FILE_MODE)

    def test_corrupted_json_and_unsupported_schema_are_not_treated_as_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            key_path = Path(directory) / "sessions" / f"{safe_entity_key('session-1')}.json"
            lock_path = Path(directory) / "sessions" / f"{safe_entity_key('session-1')}.lock"
            lock_path.touch()
            key_path.write_text("{not-json", encoding="utf-8")

            with self.assertRaises(JsonSessionStoreDataCorrupted):
                store.get("session-1")

            payload = session_to_payload(_session())
            payload["schema_version"] = 999
            atomic_write_text(key_path, dumps_payload(payload))
            with self.assertRaises(JsonSessionStoreUnsupportedSchema):
                store.get("session-1")

    def test_id_mismatch_and_temp_file_are_handled_safely(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            session_path = Path(directory) / "sessions" / f"{safe_entity_key('session-1')}.json"
            temp_path = Path(directory) / "sessions" / ".ignored.tmp"
            temp_path.write_text("not-json", encoding="utf-8")

            payload = session_to_payload(_session(session_id="other-session"))
            atomic_write_text(session_path, dumps_payload(payload))

            with self.assertRaises(JsonSessionStoreDataCorrupted):
                store.get("session-1")

    def test_atomic_write_failure_preserves_old_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            created = store.create(_session())

            failing_store = JsonFileSessionStore(
                directory,
                now_provider=_later_now,
                atomic_writer=_failing_writer,
            )
            created.context_summary = "new"

            with self.assertRaises(JsonSessionStoreIOError):
                failing_store.save(created, expected_version=0)

            self.assertEqual(store.get("session-1").version, 0)
            self.assertEqual(store.get("session-1").context_summary, "summary")


def _session(
    *,
    session_id: str = "session-1",
    version: int = 0,
) -> AgentSession:
    started_at = _fixed_now()
    return AgentSession(
        session_id=session_id,
        status=AgentSessionStatus.WAITING_CONFIRMATION,
        messages=[
            ModelMessage(role="system", content="system"),
            ModelMessage(role="user", content="user"),
            ModelMessage(
                role="assistant",
                tool_calls=(
                    ModelToolCall(
                        id="call-1",
                        name="convert_weight_unit",
                        raw_arguments='{"value":95}',
                        arguments={"value": 95},
                    ),
                ),
            ),
        ],
        pending_action_id="action-1",
        continuation=AgentContinuation(
            originating_run_id="run-1",
            assistant_message_index=2,
            next_tool_call_index=0,
            model_turns_used=1,
            tool_calls_used=0,
            started_at=started_at,
            deadline_at=started_at + timedelta(seconds=60),
            remaining_runtime_seconds=55,
        ),
        version=version,
        created_at=started_at,
        updated_at=started_at,
        context_summary="summary",
    )


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _later_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 6, tzinfo=timezone.utc)


def _failing_writer(path: Path, text: str) -> None:
    raise JsonStoreIOError("simulated write failure")


if __name__ == "__main__":
    unittest.main()
