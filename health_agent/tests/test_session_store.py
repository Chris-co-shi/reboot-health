import unittest
from datetime import datetime, timedelta, timezone

from agent.models import ModelMessage, ModelToolCall
from agent.runtime.continuation import AgentContinuation
from agent.runtime.execution_checkpoint import (
    RunExecutionCheckpoint,
    RunExecutionCheckpointPhase,
)
from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    InMemorySessionStore,
    SessionAlreadyExistsError,
    SessionNotFoundError,
    SessionVersionConflictError,
)


class AgentSessionTest(unittest.TestCase):
    def test_new_session_defaults(self) -> None:
        session = AgentSession(session_id="session-1")

        self.assertEqual(session.status, AgentSessionStatus.ACTIVE)
        self.assertEqual(session.version, 0)
        self.assertEqual(session.messages, [])
        self.assertIsNone(session.pending_action_id)
        self.assertIsNone(session.continuation)
        self.assertIsNone(session.active_run_id)
        self.assertEqual(session.run_fence_generation, 0)
        self.assertIsNone(session.active_run_last_heartbeat_at)
        self.assertIsNone(session.active_run_lease_expires_at)
        self.assertIsNone(session.execution_checkpoint)
        self.assertEqual(session.created_at.tzinfo, timezone.utc)

    def test_session_normalizes_active_run_id(self) -> None:
        heartbeat_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        session = AgentSession(
            session_id="session-1",
            status=AgentSessionStatus.RUNNING,
            active_run_id=" run-1 ",
            run_fence_generation=1,
            active_run_last_heartbeat_at=heartbeat_at,
            active_run_lease_expires_at=heartbeat_at + timedelta(seconds=60),
        )

        self.assertEqual(session.active_run_id, "run-1")
        self.assertEqual(session.run_fence_generation, 1)

    def test_non_running_session_rejects_active_owner_fields(self) -> None:
        with self.assertRaises(ValueError):
            AgentSession(session_id="session-1", active_run_id="run-1")

    def test_running_session_requires_valid_lease(self) -> None:
        heartbeat_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            AgentSession(
                session_id="session-1",
                status=AgentSessionStatus.RUNNING,
                active_run_id="run-1",
                run_fence_generation=1,
                active_run_last_heartbeat_at=heartbeat_at,
                active_run_lease_expires_at=heartbeat_at,
            )

    def test_non_running_session_rejects_execution_checkpoint(self) -> None:
        with self.assertRaises(ValueError):
            AgentSession(
                session_id="session-1",
                execution_checkpoint=_checkpoint(),
            )

    def test_running_session_checkpoint_must_match_owner_and_generation(self) -> None:
        heartbeat_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        session = AgentSession(
            session_id="session-1",
            status=AgentSessionStatus.RUNNING,
            active_run_id="run-1",
            run_fence_generation=1,
            active_run_last_heartbeat_at=heartbeat_at,
            active_run_lease_expires_at=heartbeat_at + timedelta(seconds=60),
            execution_checkpoint=_checkpoint(),
        )

        self.assertEqual(session.execution_checkpoint.originating_run_id, "run-1")
        with self.assertRaises(ValueError):
            AgentSession(
                session_id="session-1",
                status=AgentSessionStatus.RUNNING,
                active_run_id="run-other",
                run_fence_generation=1,
                active_run_last_heartbeat_at=heartbeat_at,
                active_run_lease_expires_at=heartbeat_at + timedelta(seconds=60),
                execution_checkpoint=_checkpoint(),
            )
        with self.assertRaises(ValueError):
            AgentSession(
                session_id="session-1",
                status=AgentSessionStatus.RUNNING,
                active_run_id="run-1",
                run_fence_generation=2,
                active_run_last_heartbeat_at=heartbeat_at,
                active_run_lease_expires_at=heartbeat_at + timedelta(seconds=60),
                execution_checkpoint=_checkpoint(),
            )

    def test_session_saves_complete_message_order(self) -> None:
        messages = [
            ModelMessage(role="system", content="system"),
            ModelMessage(role="user", content="user"),
            ModelMessage(role="assistant", content="assistant"),
        ]
        session = AgentSession(session_id="session-1", messages=messages)

        self.assertEqual([message.role for message in session.messages], ["system", "user", "assistant"])

    def test_assistant_tool_calls_can_be_saved(self) -> None:
        tool_call = _tool_call()
        session = AgentSession(
            session_id="session-1",
            messages=(ModelMessage(role="assistant", tool_calls=(tool_call,)),),
        )

        self.assertEqual(session.messages[0].tool_calls[0].id, "call-1")
        self.assertEqual(session.messages[0].tool_calls[0].arguments["nested"]["items"], (1,))

    def test_session_can_save_continuation(self) -> None:
        continuation = _continuation()
        session = AgentSession(session_id="session-1", continuation=continuation)

        self.assertEqual(session.continuation.next_tool_call_index, 1)

    def test_session_only_tracks_active_pending_action_id(self) -> None:
        session = AgentSession(session_id="session-1", pending_action_id=" action-1 ")

        self.assertEqual(session.pending_action_id, "action-1")
        self.assertFalse(hasattr(session, "pending_actions"))

    def test_legacy_fields_remain_available(self) -> None:
        session = AgentSession(
            session_id="session-1",
            current_skill="INITIAL_PLANNING",
            turns=2,
            pending_confirmations=["INITIAL_PLANNING"],
            context_summary="summary",
            locale="zh-CN",
        )

        self.assertEqual(session.current_skill, "INITIAL_PLANNING")
        self.assertEqual(session.turns, 2)
        self.assertEqual(session.pending_confirmations, ["INITIAL_PLANNING"])
        self.assertEqual(session.context_summary, "summary")
        self.assertEqual(session.locale, "zh-CN")


class InMemorySessionStoreTest(unittest.TestCase):
    def test_create_and_get_success(self) -> None:
        store = InMemorySessionStore()
        created = store.create(AgentSession(session_id="session-1"))
        loaded = store.get("session-1")

        self.assertEqual(created.session_id, "session-1")
        self.assertEqual(loaded.session_id, "session-1")
        self.assertIsNot(created, loaded)

    def test_duplicate_create_is_rejected(self) -> None:
        store = InMemorySessionStore()
        store.create(AgentSession(session_id="session-1"))

        with self.assertRaises(SessionAlreadyExistsError):
            store.create(AgentSession(session_id="session-1"))

    def test_get_returns_defensive_copy(self) -> None:
        store = InMemorySessionStore()
        store.create(AgentSession(session_id="session-1"))
        loaded = store.get("session-1")
        loaded.context_summary = "mutated"

        self.assertEqual(store.get("session-1").context_summary, "")

    def test_mutating_create_input_does_not_change_store(self) -> None:
        store = InMemorySessionStore()
        session = AgentSession(
            session_id="session-1",
            messages=[ModelMessage(role="user", content="original")],
        )
        store.create(session)
        session.messages.append(ModelMessage(role="assistant", content="mutated"))

        self.assertEqual(len(store.get("session-1").messages), 1)

    def test_save_with_expected_version_succeeds_once(self) -> None:
        store = InMemorySessionStore()
        session = store.create(AgentSession(session_id="session-1"))
        session.context_summary = "saved"

        saved = store.save(session, expected_version=0)

        self.assertEqual(saved.version, 1)
        self.assertEqual(store.get("session-1").version, 1)
        self.assertEqual(store.get("session-1").context_summary, "saved")

    def test_stale_expected_version_is_rejected(self) -> None:
        store = InMemorySessionStore()
        store.create(AgentSession(session_id="session-1"))
        first_reader = store.get("session-1")
        second_reader = store.get("session-1")

        first_reader.context_summary = "first"
        second_reader.context_summary = "second"
        store.save(first_reader, expected_version=0)

        with self.assertRaises(SessionVersionConflictError):
            store.save(second_reader, expected_version=0)
        self.assertEqual(store.get("session-1").context_summary, "first")

    def test_missing_session_save_is_rejected(self) -> None:
        store = InMemorySessionStore()

        with self.assertRaises(SessionNotFoundError):
            store.save(AgentSession(session_id="missing"), expected_version=0)

    def test_get_or_create_uses_copy_isolation(self) -> None:
        store = InMemorySessionStore()
        first = store.get_or_create(session_id="session-1")
        first.context_summary = "mutated"
        second = store.get_or_create(session_id="session-1")

        self.assertEqual(second.context_summary, "")

    def test_messages_and_nested_arguments_do_not_leak_references(self) -> None:
        store = InMemorySessionStore()
        arguments = {"nested": {"items": [1]}}
        session = AgentSession(
            session_id="session-1",
            messages=[
                ModelMessage(
                    role="assistant",
                    tool_calls=(_tool_call(arguments=arguments),),
                )
            ],
        )
        store.create(session)
        arguments["nested"]["items"].append(2)

        loaded = store.get("session-1")
        self.assertEqual(loaded.messages[0].tool_calls[0].arguments["nested"]["items"], (1,))
        loaded.messages.append(ModelMessage(role="assistant", content="mutated"))
        self.assertEqual(len(store.get("session-1").messages), 1)


def _tool_call(arguments: dict | None = None) -> ModelToolCall:
    return ModelToolCall(
        id="call-1",
        name="convert_weight_unit",
        raw_arguments='{"nested":{"items":[1]}}',
        arguments=arguments or {"nested": {"items": [1]}},
    )


def _continuation() -> AgentContinuation:
    started_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    return AgentContinuation(
        originating_run_id="run-1",
        assistant_message_index=2,
        next_tool_call_index=1,
        model_turns_used=1,
        tool_calls_used=1,
        started_at=started_at,
        deadline_at=started_at + timedelta(seconds=60),
    )


def _checkpoint() -> RunExecutionCheckpoint:
    started_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    return RunExecutionCheckpoint(
        checkpoint_phase=RunExecutionCheckpointPhase.DRIVE_READY,
        originating_run_id="run-1",
        run_fence_generation=1,
        assistant_message_index=None,
        next_tool_call_index=0,
        current_tool_call_id=None,
        current_tool_name=None,
        model_turns_used=0,
        tool_calls_used=0,
        remaining_runtime_seconds=60,
        started_at=started_at,
        deadline_at=started_at + timedelta(seconds=60),
        updated_at=started_at,
    )


if __name__ == "__main__":
    unittest.main()
