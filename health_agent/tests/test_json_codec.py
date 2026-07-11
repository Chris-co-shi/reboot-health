import copy
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from agent.models import ModelMessage, ModelToolCall
from agent.runtime.continuation import AgentContinuation
from agent.runtime.execution_checkpoint import (
    RunExecutionCheckpoint,
    RunExecutionCheckpointPhase,
)
from agent.runtime.pending_action import (
    PendingAction,
    PendingActionStatus,
    transition_pending_action,
)
from agent.runtime.session import AgentSession, AgentSessionStatus
from agent.runtime.storage import (
    JsonStoreDataCorrupted,
    JsonStoreUnsupportedSchema,
    PENDING_ACTION_ENTITY_TYPE,
    SESSION_ENTITY_TYPE,
    SCHEMA_VERSION,
    pending_action_from_payload,
    pending_action_to_payload,
    safe_entity_key,
    session_from_payload,
    session_to_payload,
)
from agent.tools.contract import error_content, success_content


class JsonCodecSessionTest(unittest.TestCase):
    """AgentSession JSON codec 覆盖消息、续点、枚举和时间字段。"""

    def test_session_round_trip_preserves_messages_and_continuation(self) -> None:
        session = _session()

        loaded = session_from_payload(
            session_to_payload(session),
            expected_session_id="session-1",
        )

        self.assertEqual(loaded.session_id, session.session_id)
        self.assertEqual(loaded.status, AgentSessionStatus.WAITING_CONFIRMATION)
        self.assertEqual(loaded.version, 7)
        self.assertEqual(loaded.run_fence_generation, 0)
        self.assertIsNone(loaded.active_run_id)
        self.assertIsNone(loaded.active_run_last_heartbeat_at)
        self.assertIsNone(loaded.active_run_lease_expires_at)
        self.assertIsNone(loaded.execution_checkpoint)
        self.assertEqual(loaded.created_at, session.created_at)
        self.assertEqual(loaded.updated_at, session.updated_at)
        self.assertEqual(loaded.continuation.next_tool_call_index, 1)
        self.assertEqual(loaded.continuation.remaining_runtime_seconds, 42.5)
        self.assertEqual([message.role for message in loaded.messages], ["system", "user", "assistant", "tool"])
        self.assertIsNone(loaded.messages[2].content)
        self.assertEqual(loaded.messages[3].content, "")
        self.assertEqual(len(loaded.messages[2].tool_calls), 2)
        self.assertEqual(loaded.messages[2].tool_calls[1].id, "call-2")
        self.assertEqual(loaded.messages[2].tool_calls[0].arguments["nested"]["items"], (1, 2))

    def test_session_payload_requires_supported_schema_and_entity_type(self) -> None:
        payload = session_to_payload(_session())

        bad_schema = copy.deepcopy(payload)
        bad_schema["schema_version"] = SCHEMA_VERSION + 1
        with self.assertRaises(JsonStoreUnsupportedSchema):
            session_from_payload(bad_schema)

        bad_entity = copy.deepcopy(payload)
        bad_entity["entity_type"] = PENDING_ACTION_ENTITY_TYPE
        with self.assertRaises(JsonStoreDataCorrupted):
            session_from_payload(bad_entity)

    def test_session_payload_rejects_missing_or_invalid_fields(self) -> None:
        payload = session_to_payload(_session())
        del payload["data"]["messages"]
        with self.assertRaises(JsonStoreDataCorrupted):
            session_from_payload(payload)

        payload = session_to_payload(_session())
        payload["data"]["status"] = "unknown"
        with self.assertRaises(JsonStoreDataCorrupted):
            session_from_payload(payload)

        payload = session_to_payload(_session())
        payload["data"]["created_at"] = "2026-01-02T03:04:05"
        with self.assertRaises(JsonStoreDataCorrupted):
            session_from_payload(payload)

        payload = session_to_payload(_running_session())
        payload["data"]["active_run_lease_expires_at"] = payload["data"]["active_run_last_heartbeat_at"]
        with self.assertRaises(JsonStoreDataCorrupted):
            session_from_payload(payload)

    def test_session_payload_rejects_id_mismatch_and_bad_message_shape(self) -> None:
        with self.assertRaises(JsonStoreDataCorrupted):
            session_from_payload(
                session_to_payload(_session()),
                expected_session_id="other-session",
            )

        payload = session_to_payload(_session())
        payload["data"]["messages"][3]["tool_call_id"] = None
        with self.assertRaises(JsonStoreDataCorrupted):
            session_from_payload(payload)

    def test_running_session_round_trip_preserves_lease_fields(self) -> None:
        session = _running_session()

        loaded = session_from_payload(session_to_payload(session))

        self.assertEqual(loaded.status, AgentSessionStatus.RUNNING)
        self.assertEqual(loaded.active_run_id, "run-active")
        self.assertEqual(loaded.run_fence_generation, 3)
        self.assertEqual(loaded.active_run_last_heartbeat_at, _fixed_time())
        self.assertEqual(
            loaded.active_run_lease_expires_at,
            _fixed_time() + timedelta(seconds=90),
        )
        self.assertIsNone(loaded.execution_checkpoint)

    def test_running_session_round_trip_preserves_execution_checkpoint(self) -> None:
        session = _running_session(execution_checkpoint=_checkpoint())

        loaded = session_from_payload(session_to_payload(session))

        self.assertEqual(
            loaded.execution_checkpoint.checkpoint_phase,
            RunExecutionCheckpointPhase.DRIVE_READY,
        )
        self.assertEqual(loaded.execution_checkpoint.originating_run_id, "run-active")
        self.assertEqual(loaded.execution_checkpoint.run_fence_generation, 3)
        self.assertEqual(loaded.execution_checkpoint.assistant_message_index, 1)
        self.assertEqual(loaded.execution_checkpoint.next_tool_call_index, 2)
        self.assertEqual(loaded.execution_checkpoint.model_turns_used, 4)
        self.assertEqual(loaded.execution_checkpoint.tool_calls_used, 5)
        self.assertEqual(loaded.execution_checkpoint.remaining_runtime_seconds, 12.5)

    def test_v1_session_payload_is_migrated_without_rewriting_schema(self) -> None:
        payload = session_to_payload(_session())
        payload["schema_version"] = 1
        del payload["data"]["run_fence_generation"]
        del payload["data"]["active_run_last_heartbeat_at"]
        del payload["data"]["active_run_lease_expires_at"]
        del payload["data"]["execution_checkpoint"]

        loaded = session_from_payload(payload)

        self.assertEqual(loaded.status, AgentSessionStatus.WAITING_CONFIRMATION)
        self.assertEqual(loaded.run_fence_generation, 0)
        self.assertIsNone(loaded.active_run_id)
        self.assertIsNone(loaded.execution_checkpoint)

    def test_v1_running_session_payload_is_migrated_as_stale(self) -> None:
        payload = session_to_payload(_running_session())
        payload["schema_version"] = 1
        del payload["data"]["run_fence_generation"]
        del payload["data"]["active_run_last_heartbeat_at"]
        del payload["data"]["active_run_lease_expires_at"]
        del payload["data"]["execution_checkpoint"]

        loaded = session_from_payload(payload)

        self.assertEqual(loaded.status, AgentSessionStatus.RUNNING)
        self.assertEqual(loaded.run_fence_generation, 1)
        self.assertEqual(loaded.active_run_id, "run-active")
        self.assertEqual(loaded.active_run_lease_expires_at, loaded.updated_at)
        self.assertIsNone(loaded.execution_checkpoint)

    def test_v2_session_payload_is_migrated_without_execution_checkpoint(self) -> None:
        payload = session_to_payload(_running_session())
        payload["schema_version"] = 2
        del payload["data"]["execution_checkpoint"]

        loaded = session_from_payload(payload)

        self.assertEqual(loaded.status, AgentSessionStatus.RUNNING)
        self.assertEqual(loaded.run_fence_generation, 3)
        self.assertIsNone(loaded.execution_checkpoint)


class JsonCodecPendingActionTest(unittest.TestCase):
    """PendingAction JSON codec 覆盖 arguments hash、终态结果和状态字段。"""

    def test_pending_action_round_trip_preserves_result_fields(self) -> None:
        executed = transition_pending_action(
            transition_pending_action(
                transition_pending_action(_pending_action(), PendingActionStatus.APPROVED),
                PendingActionStatus.EXECUTING,
            ),
            PendingActionStatus.EXECUTED,
            result_content=success_content({"ok": True}),
        )
        executed = replace(executed, version=3)

        loaded = pending_action_from_payload(
            pending_action_to_payload(executed),
            expected_action_id="action-1",
        )

        self.assertEqual(loaded.action_id, "action-1")
        self.assertEqual(loaded.status, PendingActionStatus.EXECUTED)
        self.assertEqual(loaded.version, 3)
        self.assertEqual(loaded.arguments_hash, executed.arguments_hash)
        self.assertEqual(loaded.result_content, success_content({"ok": True}))
        self.assertIsNone(loaded.result_error_code)
        self.assertIsNotNone(loaded.resolved_at)

    def test_pending_action_round_trip_preserves_failed_result(self) -> None:
        failed = transition_pending_action(
            transition_pending_action(_pending_action(), PendingActionStatus.APPROVED),
            PendingActionStatus.EXECUTING,
        )
        failed = transition_pending_action(
            failed,
            PendingActionStatus.FAILED,
            result_content=error_content("tool_execution_failed", "failed"),
            result_error_code="tool_execution_failed",
        )

        loaded = pending_action_from_payload(pending_action_to_payload(failed))

        self.assertEqual(loaded.status, PendingActionStatus.FAILED)
        self.assertEqual(loaded.result_error_code, "tool_execution_failed")
        self.assertIsNotNone(loaded.resolved_at)

    def test_pending_action_payload_rejects_hash_mismatch(self) -> None:
        payload = pending_action_to_payload(_pending_action())
        payload["data"]["arguments_hash"] = "0" * 64

        with self.assertRaises(JsonStoreDataCorrupted):
            pending_action_from_payload(payload)

    def test_pending_action_payload_rejects_schema_entity_and_id_mismatch(self) -> None:
        payload = pending_action_to_payload(_pending_action())
        payload["entity_type"] = SESSION_ENTITY_TYPE
        with self.assertRaises(JsonStoreDataCorrupted):
            pending_action_from_payload(payload)

        with self.assertRaises(JsonStoreDataCorrupted):
            pending_action_from_payload(
                pending_action_to_payload(_pending_action()),
                expected_action_id="other-action",
            )

    def test_safe_entity_key_is_path_safe_and_stable(self) -> None:
        first = safe_entity_key("../session/../../secret")
        second = safe_entity_key("../session/../../secret")
        other = safe_entity_key("../session/../../other")

        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 64)
        self.assertNotIn("/", first)
        self.assertNotIn("\\", first)


def _session() -> AgentSession:
    started_at = _fixed_time()
    return AgentSession(
        session_id="session-1",
        status=AgentSessionStatus.WAITING_CONFIRMATION,
        messages=[
            ModelMessage(role="system", content="system"),
            ModelMessage(role="user", content="user"),
            ModelMessage(
                role="assistant",
                content=None,
                tool_calls=(
                    _tool_call("call-1", {"nested": {"items": [1, 2]}}),
                    _tool_call("call-2", {"value": 95}),
                ),
            ),
            ModelMessage(
                role="tool",
                content="",
                name="convert_weight_unit",
                tool_call_id="call-1",
            ),
        ],
        pending_action_id="action-1",
        continuation=AgentContinuation(
            originating_run_id="run-1",
            assistant_message_index=2,
            next_tool_call_index=1,
            model_turns_used=1,
            tool_calls_used=1,
            started_at=started_at,
            deadline_at=started_at + timedelta(seconds=60),
            remaining_runtime_seconds=42.5,
        ),
        version=7,
        created_at=started_at,
        updated_at=started_at + timedelta(seconds=1),
        current_skill="INITIAL_PLANNING",
        turns=2,
        pending_confirmations=["action-1"],
        context_summary="summary",
        locale="zh-CN",
    )


def _running_session(
    *,
    execution_checkpoint: RunExecutionCheckpoint | None = None,
) -> AgentSession:
    started_at = _fixed_time()
    return AgentSession(
        session_id="session-1",
        status=AgentSessionStatus.RUNNING,
        messages=[ModelMessage(role="user", content="user")],
        active_run_id="run-active",
        run_fence_generation=3,
        active_run_last_heartbeat_at=started_at,
        active_run_lease_expires_at=started_at + timedelta(seconds=90),
        execution_checkpoint=execution_checkpoint,
        version=4,
        created_at=started_at,
        updated_at=started_at + timedelta(seconds=1),
    )


def _checkpoint() -> RunExecutionCheckpoint:
    started_at = _fixed_time()
    return RunExecutionCheckpoint(
        checkpoint_phase=RunExecutionCheckpointPhase.DRIVE_READY,
        originating_run_id="run-active",
        run_fence_generation=3,
        assistant_message_index=1,
        next_tool_call_index=2,
        current_tool_call_id=None,
        current_tool_name=None,
        model_turns_used=4,
        tool_calls_used=5,
        remaining_runtime_seconds=12.5,
        started_at=started_at,
        deadline_at=started_at + timedelta(seconds=60),
        updated_at=started_at + timedelta(seconds=1),
    )


def _pending_action() -> PendingAction:
    created_at = _fixed_time()
    return PendingAction(
        action_id="action-1",
        session_id="session-1",
        originating_run_id="run-1",
        tool_call_id="call-1",
        tool_name="record_weight_measurement",
        arguments={"value": 95, "unit": "kg"},
        assistant_message_index=2,
        tool_call_index=0,
        summary="Record weight measurement",
        created_at=created_at,
        updated_at=created_at,
        expires_at=created_at + timedelta(minutes=15),
        decision_reason="user approved",
    )


def _tool_call(call_id: str, arguments: dict) -> ModelToolCall:
    return ModelToolCall(
        id=call_id,
        name="convert_weight_unit",
        raw_arguments='{"value":95}',
        arguments=arguments,
    )


def _fixed_time() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
