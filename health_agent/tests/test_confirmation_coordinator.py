import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from agent.models import ModelMessage, ModelToolCall
from agent.runtime.confirmation import (
    ConfirmationDecision,
    ConfirmationDecisionType,
    ConfirmationResolutionStatus,
)
from agent.runtime.confirmation_coordinator import (
    CONFIRMATION_ACTION_EXPIRED,
    CONFIRMATION_ACTION_NOT_FOUND,
    CONFIRMATION_CONTINUATION_INVALID,
    CONFIRMATION_DECISION_CONFLICT,
    CONFIRMATION_PERMISSION_CHANGED,
    CONFIRMATION_SESSION_MISMATCH,
    CONFIRMATION_SESSION_NOT_FOUND,
    CONFIRMATION_SNAPSHOT_MISMATCH,
    CONFIRMATION_TOOL_NOT_FOUND,
    CONFIRMATION_TOOL_RESULT_MISMATCH,
    TOOL_EXECUTION_STATE_UNKNOWN,
    TOOL_REJECTED_BY_USER,
    ConfirmationCoordinator,
)
from agent.runtime.continuation import AgentContinuation
from agent.runtime.pending_action import PendingAction, PendingActionStatus
from agent.runtime.pending_action_store import InMemoryPendingActionStore
from agent.runtime.pending_action_store import PendingActionStoreError
from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    InMemorySessionStore,
    SessionStoreError,
)
from agent.tools.contract import ToolDefinition, ToolPermission
from agent.tools.registry import ToolRegistry


class ConfirmationCoordinatorApproveRejectTest(unittest.TestCase):
    def test_approve_executes_once_and_advances_session(self) -> None:
        calls: list[Mapping[str, Any]] = []
        session_store, pending_store = _stores()
        coordinator = _coordinator(session_store, pending_store, calls=calls)

        result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(result.status, ConfirmationResolutionStatus.RESOLVED)
        self.assertTrue(result.tool_succeeded)
        self.assertEqual(calls, [{"value": 95, "unit": "kg"}])
        action = pending_store.get("action-1")
        self.assertEqual(action.status, PendingActionStatus.EXECUTED)
        self.assertEqual(action.version, 3)
        self.assertIsNotNone(action.result_content)
        self.assertIsNone(action.result_error_code)
        self.assertNotIn("arguments", json.dumps(result.to_dict()))

        session = session_store.get("session-1")
        self.assertEqual(session.status, AgentSessionStatus.ACTIVE)
        self.assertIsNone(session.pending_action_id)
        self.assertEqual([message.role for message in session.messages], ["system", "user", "assistant", "tool"])
        self.assertEqual(session.messages[-1].tool_call_id, "call-1")
        self.assertEqual(session.continuation.next_tool_call_index, 1)
        self.assertEqual(session.continuation.tool_calls_used, 1)
        self.assertEqual(session.continuation.model_turns_used, 1)
        self.assertEqual(session.continuation.remaining_runtime_seconds, 30)

    def test_approve_after_read_only_tool_consumes_second_tool_call(self) -> None:
        calls: list[Mapping[str, Any]] = []
        session_store, pending_store = _stores(tool_call_index=1, tool_calls_used=1)
        coordinator = _coordinator(session_store, pending_store, calls=calls)

        result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        session = session_store.get("session-1")
        self.assertEqual(result.status, ConfirmationResolutionStatus.RESOLVED)
        self.assertEqual(session.continuation.next_tool_call_index, 2)
        self.assertEqual(session.continuation.tool_calls_used, 2)
        self.assertEqual(session.continuation.model_turns_used, 1)
        self.assertEqual(session.continuation.remaining_runtime_seconds, 30)

    def test_reject_saves_rejection_result_without_calling_handler(self) -> None:
        calls: list[Mapping[str, Any]] = []
        session_store, pending_store = _stores()
        coordinator = _coordinator(session_store, pending_store, calls=calls)

        result = coordinator.resolve(
            _decision(
                ConfirmationDecisionType.REJECT,
                reason="用户写了很长的私有原因",
            )
        )

        self.assertEqual(result.status, ConfirmationResolutionStatus.REJECTED)
        self.assertFalse(result.tool_succeeded)
        self.assertEqual(calls, [])
        action = pending_store.get("action-1")
        self.assertEqual(action.status, PendingActionStatus.REJECTED)
        self.assertEqual(action.result_error_code, TOOL_REJECTED_BY_USER)
        self.assertEqual(action.decision_reason, "用户写了很长的私有原因")
        session = session_store.get("session-1")
        self.assertEqual(session.status, AgentSessionStatus.ACTIVE)
        self.assertIsNone(session.pending_action_id)
        self.assertEqual(session.continuation.next_tool_call_index, 1)
        self.assertEqual(session.continuation.tool_calls_used, 1)
        content = session.messages[-1].content
        self.assertEqual(json.loads(content)["error"]["code"], TOOL_REJECTED_BY_USER)
        self.assertNotIn("私有原因", content)
        self.assertNotIn("arguments", json.dumps(result.to_dict(), ensure_ascii=False))


class ConfirmationCoordinatorBindingTest(unittest.TestCase):
    def test_missing_session_fails_closed(self) -> None:
        coordinator = ConfirmationCoordinator(
            session_store=InMemorySessionStore(),
            pending_action_store=InMemoryPendingActionStore(),
            tool_registry=_registry([]),
            now_provider=_fixed_now,
        )

        result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(result.error.code, CONFIRMATION_SESSION_NOT_FOUND)

    def test_missing_action_fails_closed(self) -> None:
        session_store = InMemorySessionStore()
        session_store.create(_session())
        coordinator = ConfirmationCoordinator(
            session_store=session_store,
            pending_action_store=InMemoryPendingActionStore(),
            tool_registry=_registry([]),
            now_provider=_fixed_now,
        )

        result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(result.error.code, CONFIRMATION_ACTION_NOT_FOUND)

    def test_binding_mismatches_never_call_handler(self) -> None:
        scenarios = [
            ("not_waiting", _session(status=AgentSessionStatus.ACTIVE), _action(), CONFIRMATION_SESSION_MISMATCH),
            ("pending_id_mismatch", _session(pending_action_id="other"), _action(), CONFIRMATION_SESSION_MISMATCH),
            ("action_session_mismatch", _session(), _action(session_id="other"), CONFIRMATION_SESSION_MISMATCH),
            ("missing_continuation", _session(continuation=None), _action(), CONFIRMATION_CONTINUATION_INVALID),
            ("assistant_index_invalid", _session(assistant_message_index=9), _action(), CONFIRMATION_CONTINUATION_INVALID),
            ("assistant_role_invalid", _session(assistant_role="user"), _action(), CONFIRMATION_CONTINUATION_INVALID),
            ("tool_index_invalid", _session(continuation=_continuation(tool_call_index=9)), _action(), CONFIRMATION_CONTINUATION_INVALID),
            ("tool_id_mismatch", _session(tool_call_id="other"), _action(), CONFIRMATION_SNAPSHOT_MISMATCH),
            ("tool_name_mismatch", _session(tool_name="other_tool"), _action(), CONFIRMATION_SNAPSHOT_MISMATCH),
            ("arguments_hash_mismatch", _session(arguments={"value": 96, "unit": "kg"}), _action(), CONFIRMATION_SNAPSHOT_MISMATCH),
        ]
        for name, session, action, expected_code in scenarios:
            with self.subTest(name=name):
                calls: list[Mapping[str, Any]] = []
                session_store = InMemorySessionStore()
                pending_store = InMemoryPendingActionStore()
                session_store.create(session)
                pending_store.create(action)
                coordinator = _coordinator(session_store, pending_store, calls=calls)

                result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

                self.assertEqual(result.error.code, expected_code)
                self.assertEqual(calls, [])

    def test_tool_deleted_or_permission_changed_fails_closed(self) -> None:
        for registry, expected_code in (
            (ToolRegistry(), CONFIRMATION_TOOL_NOT_FOUND),
            (_registry([], permission=ToolPermission.READ_ONLY), CONFIRMATION_PERMISSION_CHANGED),
        ):
            with self.subTest(expected_code=expected_code):
                calls: list[Mapping[str, Any]] = []
                session_store, pending_store = _stores()
                coordinator = ConfirmationCoordinator(
                    session_store=session_store,
                    pending_action_store=pending_store,
                    tool_registry=registry,
                    now_provider=_fixed_now,
                )

                result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

                self.assertEqual(result.error.code, expected_code)
                self.assertEqual(calls, [])


class ConfirmationCoordinatorIdempotencyTest(unittest.TestCase):
    def test_repeated_approve_uses_saved_result_without_reexecuting(self) -> None:
        calls: list[Mapping[str, Any]] = []
        session_store, pending_store = _stores()
        coordinator = _coordinator(session_store, pending_store, calls=calls)
        first = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        second = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(first.status, ConfirmationResolutionStatus.RESOLVED)
        self.assertEqual(second.status, ConfirmationResolutionStatus.RESOLVED)
        self.assertEqual(len(calls), 1)
        session = session_store.get("session-1")
        self.assertEqual([message.role for message in session.messages].count("tool"), 1)

    def test_repeated_reject_replays_without_duplicate_message(self) -> None:
        calls: list[Mapping[str, Any]] = []
        session_store, pending_store = _stores()
        coordinator = _coordinator(session_store, pending_store, calls=calls)
        coordinator.resolve(_decision(ConfirmationDecisionType.REJECT))

        result = coordinator.resolve(_decision(ConfirmationDecisionType.REJECT))

        self.assertEqual(result.status, ConfirmationResolutionStatus.REJECTED)
        self.assertEqual(calls, [])
        session = session_store.get("session-1")
        self.assertEqual([message.role for message in session.messages].count("tool"), 1)

    def test_conflicting_terminal_decisions_are_rejected(self) -> None:
        session_store, pending_store = _stores()
        coordinator = _coordinator(session_store, pending_store)
        coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        result = coordinator.resolve(_decision(ConfirmationDecisionType.REJECT))

        self.assertEqual(result.status, ConfirmationResolutionStatus.CONFLICT)
        self.assertEqual(result.error.code, CONFIRMATION_DECISION_CONFLICT)

    def test_existing_tool_message_content_mismatch_fails_closed(self) -> None:
        session_store, pending_store = _stores()
        coordinator = _coordinator(session_store, pending_store)
        coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))
        session = session_store.get("session-1")
        session.messages[-1] = ModelMessage(
            role="tool",
            tool_call_id="call-1",
            name=TOOL_NAME,
            content='{"success":true,"data":{"changed":true}}',
        )
        session_store.save(session, expected_version=session.version)

        result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(result.error.code, CONFIRMATION_TOOL_RESULT_MISMATCH)

    def test_session_save_failure_after_executed_recovers_without_reexecution(self) -> None:
        calls: list[Mapping[str, Any]] = []
        session_store, pending_store = _stores(session_store=FailFirstActiveSaveSessionStore())
        coordinator = _coordinator(session_store, pending_store, calls=calls)

        first = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))
        second = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(first.status, ConfirmationResolutionStatus.FAILED)
        self.assertEqual(second.status, ConfirmationResolutionStatus.RESOLVED)
        self.assertEqual(len(calls), 1)
        self.assertEqual(pending_store.get("action-1").status, PendingActionStatus.EXECUTED)
        self.assertEqual(session_store.get("session-1").status, AgentSessionStatus.ACTIVE)

    def test_action_save_failure_before_execution_does_not_call_handler(self) -> None:
        calls: list[Mapping[str, Any]] = []
        session_store, pending_store = _stores(
            pending_store=FailOnStatusPendingActionStore(PendingActionStatus.APPROVED)
        )
        coordinator = _coordinator(session_store, pending_store, calls=calls)

        result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(result.status, ConfirmationResolutionStatus.FAILED)
        self.assertEqual(calls, [])
        self.assertEqual(pending_store.get("action-1").status, PendingActionStatus.PENDING)

    def test_final_action_save_failure_returns_state_unknown(self) -> None:
        calls: list[Mapping[str, Any]] = []
        session_store, pending_store = _stores(
            pending_store=FailOnStatusPendingActionStore(PendingActionStatus.EXECUTED)
        )
        coordinator = _coordinator(session_store, pending_store, calls=calls)

        result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(result.status, ConfirmationResolutionStatus.FAILED)
        self.assertEqual(result.error.code, TOOL_EXECUTION_STATE_UNKNOWN)
        self.assertEqual(len(calls), 1)
        self.assertEqual(pending_store.get("action-1").status, PendingActionStatus.EXECUTING)
        self.assertEqual(session_store.get("session-1").status, AgentSessionStatus.WAITING_CONFIRMATION)

    def test_handler_failure_is_saved_and_repeated_approve_does_not_retry(self) -> None:
        calls: list[Mapping[str, Any]] = []
        session_store, pending_store = _stores()
        coordinator = ConfirmationCoordinator(
            session_store=session_store,
            pending_action_store=pending_store,
            tool_registry=_failing_registry(calls),
            now_provider=_fixed_now,
        )

        first = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))
        second = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(first.status, ConfirmationResolutionStatus.RESOLVED)
        self.assertFalse(first.tool_succeeded)
        self.assertEqual(second.status, ConfirmationResolutionStatus.RESOLVED)
        self.assertEqual(len(calls), 1)
        self.assertEqual(pending_store.get("action-1").status, PendingActionStatus.FAILED)

    def test_executing_state_fails_closed_without_retry(self) -> None:
        calls: list[Mapping[str, Any]] = []
        session_store, pending_store = _stores(action_status=PendingActionStatus.EXECUTING)
        coordinator = _coordinator(session_store, pending_store, calls=calls)

        result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(result.status, ConfirmationResolutionStatus.FAILED)
        self.assertEqual(result.error.code, TOOL_EXECUTION_STATE_UNKNOWN)
        self.assertEqual(calls, [])


class ConfirmationCoordinatorExpiryTest(unittest.TestCase):
    def test_now_before_expires_allows_approve(self) -> None:
        session_store, pending_store = _stores()
        coordinator = _coordinator(session_store, pending_store, now=_fixed_now)

        result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(result.status, ConfirmationResolutionStatus.RESOLVED)

    def test_now_equal_expires_marks_expired_without_handler(self) -> None:
        calls: list[Mapping[str, Any]] = []
        expires_at = _fixed_time() + timedelta(minutes=15)
        session_store, pending_store = _stores(expires_at=expires_at)
        coordinator = _coordinator(
            session_store,
            pending_store,
            calls=calls,
            now=lambda: expires_at,
        )

        result = coordinator.resolve(_decision(ConfirmationDecisionType.APPROVE))

        self.assertEqual(result.status, ConfirmationResolutionStatus.EXPIRED)
        self.assertEqual(result.error.code, CONFIRMATION_ACTION_EXPIRED)
        self.assertEqual(pending_store.get("action-1").status, PendingActionStatus.EXPIRED)
        self.assertEqual(calls, [])
        self.assertEqual(session_store.get("session-1").status, AgentSessionStatus.WAITING_CONFIRMATION)

    def test_expired_reject_does_not_mark_rejected(self) -> None:
        calls: list[Mapping[str, Any]] = []
        expires_at = _fixed_time() + timedelta(minutes=15)
        session_store, pending_store = _stores(expires_at=expires_at)
        coordinator = _coordinator(
            session_store,
            pending_store,
            calls=calls,
            now=lambda: expires_at,
        )

        result = coordinator.resolve(_decision(ConfirmationDecisionType.REJECT))

        self.assertEqual(result.status, ConfirmationResolutionStatus.EXPIRED)
        self.assertEqual(pending_store.get("action-1").status, PendingActionStatus.EXPIRED)
        self.assertEqual(calls, [])


class FailFirstActiveSaveSessionStore(InMemorySessionStore):
    """第一次保存 ACTIVE Session 时失败，用于模拟 Action 已终态但 Session 未保存。"""

    def __init__(self) -> None:
        super().__init__()
        self.failed = False

    def save(self, session: AgentSession, expected_version: int) -> AgentSession:
        if session.status == AgentSessionStatus.ACTIVE and not self.failed:
            self.failed = True
            raise SessionStoreError("forced active save failure")
        return super().save(session, expected_version)


class FailOnStatusPendingActionStore(InMemoryPendingActionStore):
    """保存指定状态时失败一次，用于模拟 Action CAS/持久化窗口。"""

    def __init__(self, status: PendingActionStatus) -> None:
        super().__init__()
        self.status = status
        self.failed = False

    def save(self, action: PendingAction, expected_version: int) -> PendingAction:
        if action.status == self.status and not self.failed:
            self.failed = True
            raise PendingActionStoreError("forced action save failure")
        return super().save(action, expected_version)


TOOL_NAME = "record_weight_measurement"


def _stores(
    *,
    session_store: InMemorySessionStore | None = None,
    pending_store: InMemoryPendingActionStore | None = None,
    tool_call_index: int = 0,
    tool_calls_used: int = 0,
    action_status: PendingActionStatus = PendingActionStatus.PENDING,
    expires_at: datetime | None = None,
) -> tuple[InMemorySessionStore, InMemoryPendingActionStore]:
    session_store = session_store or InMemorySessionStore()
    pending_store = pending_store or InMemoryPendingActionStore()
    session_store.create(
        _session(
            tool_call_index=tool_call_index,
            tool_calls_used=tool_calls_used,
        )
    )
    pending_store.create(
        _action(
            tool_call_index=tool_call_index,
            status=action_status,
            expires_at=expires_at or _fixed_time() + timedelta(minutes=15),
        )
    )
    return session_store, pending_store


def _coordinator(
    session_store: InMemorySessionStore,
    pending_store: InMemoryPendingActionStore,
    *,
    calls: list[Mapping[str, Any]] | None = None,
    now=None,
) -> ConfirmationCoordinator:
    return ConfirmationCoordinator(
        session_store=session_store,
        pending_action_store=pending_store,
        tool_registry=_registry(calls if calls is not None else []),
        now_provider=now or _fixed_now,
    )


def _decision(decision: ConfirmationDecisionType, reason: str | None = None) -> ConfirmationDecision:
    return ConfirmationDecision(
        session_id="session-1",
        action_id="action-1",
        decision=decision,
        reason=reason,
    )


def _registry(
    calls: list[Mapping[str, Any]],
    *,
    permission: ToolPermission = ToolPermission.CONFIRMATION_REQUIRED,
) -> ToolRegistry:
    def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        calls.append(arguments)
        return {"recorded": True, "value": arguments["value"]}

    return ToolRegistry(
        [
            ToolDefinition(
                name=TOOL_NAME,
                description="Record weight after confirmation",
                input_schema={"type": "object"},
                permission=permission,
                handler=handler,
            )
        ]
    )


def _failing_registry(calls: list[Mapping[str, Any]]) -> ToolRegistry:
    def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        calls.append(arguments)
        raise RuntimeError("private failure")

    return ToolRegistry(
        [
            ToolDefinition(
                name=TOOL_NAME,
                description="Fail after confirmation",
                input_schema={"type": "object"},
                permission=ToolPermission.CONFIRMATION_REQUIRED,
                handler=handler,
            )
        ]
    )


def _session(
    *,
    status: AgentSessionStatus = AgentSessionStatus.WAITING_CONFIRMATION,
    pending_action_id: str | None = "action-1",
    continuation: AgentContinuation | None | object = ...,
    assistant_message_index: int = 2,
    tool_call_index: int = 0,
    tool_calls_used: int = 0,
    tool_call_id: str = "call-1",
    tool_name: str = TOOL_NAME,
    assistant_role: str = "assistant",
    arguments: Mapping[str, Any] | None = None,
) -> AgentSession:
    if continuation is ...:
        continuation = _continuation(
            assistant_message_index=assistant_message_index,
            tool_call_index=tool_call_index,
            tool_calls_used=tool_calls_used,
        )
    tool_calls = [
        _tool_call(id=f"read-{index}", name="read_tool", arguments={"value": index})
        for index in range(tool_call_index)
    ]
    tool_calls.append(
        _tool_call(
            id=tool_call_id,
            name=tool_name,
            arguments=arguments or {"value": 95, "unit": "kg"},
        )
    )
    tool_calls.append(_tool_call(id="later-1", name="read_tool", arguments={"value": 2}))
    return AgentSession(
        session_id="session-1",
        status=status,
        messages=[
            ModelMessage(role="system", content="system"),
            ModelMessage(role="user", content="user"),
            ModelMessage(
                role=assistant_role,
                content=None,
                tool_calls=tuple(tool_calls) if assistant_role == "assistant" else (),
            ),
        ],
        pending_action_id=pending_action_id,
        continuation=continuation,
    )


def _continuation(
    *,
    assistant_message_index: int = 2,
    tool_call_index: int = 0,
    tool_calls_used: int = 0,
) -> AgentContinuation:
    started_at = _fixed_time()
    return AgentContinuation(
        originating_run_id="run-1",
        assistant_message_index=assistant_message_index,
        next_tool_call_index=tool_call_index,
        model_turns_used=1,
        tool_calls_used=tool_calls_used,
        started_at=started_at,
        deadline_at=started_at + timedelta(seconds=60),
        remaining_runtime_seconds=30,
    )


def _action(**overrides) -> PendingAction:
    created_at = _fixed_time()
    data = {
        "action_id": "action-1",
        "session_id": "session-1",
        "originating_run_id": "run-1",
        "tool_call_id": "call-1",
        "tool_name": TOOL_NAME,
        "arguments": {"value": 95, "unit": "kg"},
        "assistant_message_index": 2,
        "tool_call_index": 0,
        "summary": "Record weight",
        "expires_at": created_at + timedelta(minutes=15),
        "created_at": created_at,
        "updated_at": created_at,
    }
    data.update(overrides)
    return PendingAction(**data)


def _tool_call(id: str, name: str, arguments: Mapping[str, Any]) -> ModelToolCall:
    return ModelToolCall(
        id=id,
        name=name,
        raw_arguments=json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        arguments=arguments,
    )


def _fixed_now() -> datetime:
    return _fixed_time() + timedelta(minutes=1)


def _fixed_time() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
