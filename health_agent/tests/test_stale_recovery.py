import unittest
from datetime import datetime, timedelta, timezone

from agent.models import ModelMessage, ModelResponse, ModelToolCall
from agent.runtime.execution_checkpoint import (
    RunExecutionCheckpoint,
    RunExecutionCheckpointPhase,
)
from agent.runtime.generic_loop import (
    ERROR_SESSION_FINALIZATION_STATE_UNKNOWN,
    ERROR_SESSION_RECOVERY_MODEL_STATE_UNKNOWN,
    ERROR_SESSION_RECOVERY_NOT_ELIGIBLE,
    ERROR_SESSION_RECOVERY_TOOL_STATE_UNKNOWN,
    GENERIC_STATUS_COMPLETED,
    GENERIC_STATUS_FAILED,
    GenericAgentLoop,
)
from agent.runtime.run_ownership import RunOwnership
from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    InMemorySessionStore,
    SessionRunFenceLostError,
)
from agent.runtime.stale_recovery import StaleRecoveryClassification
from tests.support.scripted_model_provider import ScriptedModelProvider


class StaleRecoveryTest(unittest.TestCase):
    """stale RUNNING Session 只允许从 DRIVE_READY checkpoint 自动恢复。"""

    def test_inspect_classifies_stale_checkpoint_phases(self) -> None:
        for phase, classification in (
            (
                RunExecutionCheckpointPhase.DRIVE_READY,
                StaleRecoveryClassification.SAFE_RESUME,
            ),
            (
                RunExecutionCheckpointPhase.MODEL_CALL_IN_FLIGHT,
                StaleRecoveryClassification.MODEL_STATE_UNKNOWN,
            ),
            (
                RunExecutionCheckpointPhase.TOOL_CALL_IN_FLIGHT,
                StaleRecoveryClassification.TOOL_STATE_UNKNOWN,
            ),
            (
                RunExecutionCheckpointPhase.FINALIZING,
                StaleRecoveryClassification.FINALIZATION_STATE_UNKNOWN,
            ),
        ):
            with self.subTest(phase=phase):
                store = InMemorySessionStore()
                store.create(_stale_session(_checkpoint(phase)))
                loop = _loop(ScriptedModelProvider([]), store)

                inspection = loop.inspect_stale_session("session-1")

                self.assertEqual(inspection.classification, classification)
                self.assertEqual(inspection.checkpoint_phase, phase.name)

    def test_safe_drive_ready_recovery_continues_without_new_user_or_duplicate_tool(self) -> None:
        store = InMemorySessionStore()
        old_session = store.create(
            _stale_session(
                _checkpoint(
                    RunExecutionCheckpointPhase.DRIVE_READY,
                    assistant_message_index=2,
                    next_tool_call_index=1,
                    model_turns_used=1,
                    tool_calls_used=1,
                ),
                messages=_messages_with_completed_tool(),
            )
        )
        provider = ScriptedModelProvider(
            [ModelResponse(content="恢复完成", finish_reason="stop")]
        )
        loop = _loop(provider, store)

        result = loop.recover_stale_session("session-1")
        stored = store.get("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_COMPLETED)
        self.assertEqual(result.model_turns, 2)
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual([message.role for message in stored.messages], [
            "system",
            "user",
            "assistant",
            "tool",
            "assistant",
        ])
        self.assertEqual(stored.run_fence_generation, 2)
        self.assertIsNone(stored.active_run_id)
        self.assertIsNone(stored.execution_checkpoint)
        self.assertEqual(
            provider.calls[0]["messages"][1].content,
            "原始任务",
        )

        old_session.context_summary = "old write"
        with self.assertRaises(SessionRunFenceLostError):
            loop._save_owned_session(  # noqa: SLF001 - fencing 合同测试。
                old_session,
                RunOwnership("session-1", "run-old", 1),
            )

    def test_model_in_flight_recovery_is_state_unknown_without_provider_call(self) -> None:
        store = InMemorySessionStore()
        store.create(_stale_session(_checkpoint(RunExecutionCheckpointPhase.MODEL_CALL_IN_FLIGHT)))
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop = _loop(provider, store)

        result = loop.recover_stale_session("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_RECOVERY_MODEL_STATE_UNKNOWN)
        self.assertEqual(len(provider.calls), 0)
        self.assertEqual(store.get("session-1").active_run_id, "run-old")

    def test_tool_in_flight_recovery_is_state_unknown_without_handler_call(self) -> None:
        store = InMemorySessionStore()
        store.create(_stale_session(_checkpoint(RunExecutionCheckpointPhase.TOOL_CALL_IN_FLIGHT)))
        loop = _loop(ScriptedModelProvider([]), store)

        result = loop.recover_stale_session("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_RECOVERY_TOOL_STATE_UNKNOWN)
        self.assertEqual(store.get("session-1").active_run_id, "run-old")

    def test_finalizing_recovery_reports_finalization_state_unknown(self) -> None:
        store = InMemorySessionStore()
        store.create(_stale_session(_checkpoint(RunExecutionCheckpointPhase.FINALIZING)))
        loop = _loop(ScriptedModelProvider([]), store)

        result = loop.recover_stale_session("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_FINALIZATION_STATE_UNKNOWN)
        self.assertEqual(store.get("session-1").active_run_id, "run-old")

    def test_missing_checkpoint_is_not_recovered(self) -> None:
        store = InMemorySessionStore()
        store.create(_stale_session(None))
        provider = ScriptedModelProvider([ModelResponse(content="不应调用")])
        loop = _loop(provider, store)

        result = loop.recover_stale_session("session-1")

        self.assertEqual(result.status, GENERIC_STATUS_FAILED)
        self.assertEqual(result.error.code, ERROR_SESSION_RECOVERY_NOT_ELIGIBLE)
        self.assertEqual(len(provider.calls), 0)

    def test_valid_lease_is_not_recovered(self) -> None:
        store = InMemorySessionStore()
        store.create(
            _stale_session(
                _checkpoint(RunExecutionCheckpointPhase.DRIVE_READY),
                lease_expires_at=_fixed_now() + timedelta(seconds=60),
            )
        )
        loop = _loop(ScriptedModelProvider([]), store)

        result = loop.recover_stale_session("session-1")

        self.assertEqual(result.error.code, ERROR_SESSION_RECOVERY_NOT_ELIGIBLE)
        self.assertEqual(store.get("session-1").run_fence_generation, 1)


def _loop(
    provider: ScriptedModelProvider,
    store: InMemorySessionStore,
) -> GenericAgentLoop:
    return GenericAgentLoop(
        provider=provider,
        session_store=store,
        now_provider=_fixed_now,
        monotonic_provider=lambda: 100.0,
        run_lease_ttl_seconds=90,
        run_lease_heartbeat_interval_seconds=10,
        lease_safety_margin_seconds=1,
    )


def _stale_session(
    checkpoint: RunExecutionCheckpoint | None,
    *,
    messages: list[ModelMessage] | None = None,
    lease_expires_at: datetime | None = None,
) -> AgentSession:
    heartbeat_at = _fixed_now() - timedelta(seconds=120)
    return AgentSession(
        session_id="session-1",
        status=AgentSessionStatus.RUNNING,
        messages=messages or [ModelMessage(role="user", content="原始任务")],
        active_run_id="run-old",
        run_fence_generation=1,
        active_run_last_heartbeat_at=heartbeat_at,
        active_run_lease_expires_at=lease_expires_at or _fixed_now(),
        execution_checkpoint=checkpoint,
        created_at=heartbeat_at,
        updated_at=heartbeat_at,
    )


def _checkpoint(
    phase: RunExecutionCheckpointPhase,
    *,
    assistant_message_index: int | None = None,
    next_tool_call_index: int = 0,
    model_turns_used: int = 0,
    tool_calls_used: int = 0,
) -> RunExecutionCheckpoint:
    current_tool_call_id = "call-1" if phase == RunExecutionCheckpointPhase.TOOL_CALL_IN_FLIGHT else None
    current_tool_name = "read_metric" if phase == RunExecutionCheckpointPhase.TOOL_CALL_IN_FLIGHT else None
    return RunExecutionCheckpoint(
        checkpoint_phase=phase,
        originating_run_id="run-old",
        run_fence_generation=1,
        assistant_message_index=assistant_message_index,
        next_tool_call_index=next_tool_call_index,
        current_tool_call_id=current_tool_call_id,
        current_tool_name=current_tool_name,
        model_turns_used=model_turns_used,
        tool_calls_used=tool_calls_used,
        remaining_runtime_seconds=60,
        started_at=_fixed_now() - timedelta(seconds=30),
        deadline_at=_fixed_now() + timedelta(seconds=30),
        updated_at=_fixed_now() - timedelta(seconds=120),
    )


def _messages_with_completed_tool() -> list[ModelMessage]:
    return [
        ModelMessage(role="system", content="system"),
        ModelMessage(role="user", content="原始任务"),
        ModelMessage(
            role="assistant",
            tool_calls=(
                ModelToolCall(
                    id="call-1",
                    name="read_metric",
                    raw_arguments='{"value":7}',
                    arguments={"value": 7},
                ),
            ),
        ),
        ModelMessage(
            role="tool",
            name="read_metric",
            tool_call_id="call-1",
            content='{"success": true, "data": {"value": 7}}',
        ),
    ]


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
