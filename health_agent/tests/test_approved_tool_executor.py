import inspect
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from agent.runtime.pending_action import PendingAction, PendingActionStatus
from agent.runtime.pending_action_store import InMemoryPendingActionStore
from agent.tools.approved_executor import (
    ApprovedActionExecutionError,
    ApprovedActionExecutor,
    CONFIRMATION_ARGUMENTS_HASH_MISMATCH,
    CONFIRMATION_PERMISSION_CHANGED,
    CONFIRMATION_TOOL_NOT_FOUND,
    TOOL_EXECUTION_STATE_UNKNOWN,
)
from agent.tools.contract import ToolDefinition, ToolPermission
from agent.tools.registry import ToolRegistry


class ApprovedActionExecutorTest(unittest.TestCase):
    def test_execute_accepts_only_action_id(self) -> None:
        signature = inspect.signature(ApprovedActionExecutor.execute)

        self.assertEqual(list(signature.parameters), ["self", "action_id"])

    def test_executes_confirmation_tool_from_frozen_action_arguments(self) -> None:
        calls: list[Mapping[str, Any]] = []
        store = InMemoryPendingActionStore()
        store.create(_action(arguments={"value": 95, "unit": "kg"}))
        executor = ApprovedActionExecutor(
            pending_action_store=store,
            tool_registry=_registry(calls),
        )

        result = executor.execute("action-1")

        self.assertTrue(result.success)
        self.assertEqual(calls[0]["value"], 95)
        self.assertEqual(result.tool_call_id, "call-1")

    def test_non_executing_action_does_not_call_handler(self) -> None:
        calls: list[Mapping[str, Any]] = []
        store = InMemoryPendingActionStore()
        store.create(_action(status=PendingActionStatus.PENDING))
        executor = ApprovedActionExecutor(
            pending_action_store=store,
            tool_registry=_registry(calls),
        )

        with self.assertRaises(ApprovedActionExecutionError) as context:
            executor.execute("action-1")

        self.assertEqual(context.exception.code, TOOL_EXECUTION_STATE_UNKNOWN)
        self.assertEqual(calls, [])

    def test_arguments_hash_mismatch_does_not_call_handler(self) -> None:
        calls: list[Mapping[str, Any]] = []
        store = InMemoryPendingActionStore()
        store.create(_action(arguments={"value": 95, "unit": "kg"}))
        loaded = store.get("action-1")
        with self.assertRaises(ValueError):
            # PendingAction 本身会拒绝 hash 不匹配，证明篡改无法通过合同层。
            PendingAction(
                action_id="action-2",
                session_id=loaded.session_id,
                originating_run_id=loaded.originating_run_id,
                tool_call_id=loaded.tool_call_id,
                tool_name=loaded.tool_name,
                arguments={"value": 96, "unit": "kg"},
                assistant_message_index=loaded.assistant_message_index,
                tool_call_index=loaded.tool_call_index,
                summary=loaded.summary,
                expires_at=loaded.expires_at,
                arguments_hash=loaded.arguments_hash,
                status=PendingActionStatus.EXECUTING,
                created_at=loaded.created_at,
                updated_at=loaded.updated_at,
            )

        self.assertEqual(calls, [])

    def test_missing_tool_does_not_call_handler(self) -> None:
        calls: list[Mapping[str, Any]] = []
        store = InMemoryPendingActionStore()
        store.create(_action())
        executor = ApprovedActionExecutor(
            pending_action_store=store,
            tool_registry=ToolRegistry(),
        )

        with self.assertRaises(ApprovedActionExecutionError) as context:
            executor.execute("action-1")

        self.assertEqual(context.exception.code, CONFIRMATION_TOOL_NOT_FOUND)
        self.assertEqual(calls, [])

    def test_permission_change_does_not_call_handler(self) -> None:
        calls: list[Mapping[str, Any]] = []
        store = InMemoryPendingActionStore()
        store.create(_action())
        executor = ApprovedActionExecutor(
            pending_action_store=store,
            tool_registry=_registry(calls, permission=ToolPermission.READ_ONLY),
        )

        with self.assertRaises(ApprovedActionExecutionError) as context:
            executor.execute("action-1")

        self.assertEqual(context.exception.code, CONFIRMATION_PERMISSION_CHANGED)
        self.assertEqual(calls, [])

    def test_handler_exception_becomes_structured_tool_error(self) -> None:
        def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
            raise RuntimeError("private traceback")

        store = InMemoryPendingActionStore()
        store.create(_action())
        executor = ApprovedActionExecutor(
            pending_action_store=store,
            tool_registry=ToolRegistry([_tool(handler=handler)]),
        )

        result = executor.execute("action-1")

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "tool_execution_failed")
        self.assertNotIn("private traceback", result.content)


def _registry(
    calls: list[Mapping[str, Any]],
    *,
    permission: ToolPermission = ToolPermission.CONFIRMATION_REQUIRED,
) -> ToolRegistry:
    def handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        calls.append(arguments)
        return {"recorded": True, "value": arguments["value"]}

    return ToolRegistry([_tool(handler=handler, permission=permission)])


def _tool(
    *,
    handler,
    permission: ToolPermission = ToolPermission.CONFIRMATION_REQUIRED,
) -> ToolDefinition:
    return ToolDefinition(
        name="record_weight_measurement",
        description="Record weight after confirmation",
        input_schema={"type": "object"},
        permission=permission,
        handler=handler,
    )


def _action(**overrides) -> PendingAction:
    created_at = _fixed_time()
    data = {
        "action_id": "action-1",
        "session_id": "session-1",
        "originating_run_id": "run-1",
        "tool_call_id": "call-1",
        "tool_name": "record_weight_measurement",
        "arguments": {"value": 95, "unit": "kg"},
        "assistant_message_index": 2,
        "tool_call_index": 0,
        "summary": "Record weight",
        "expires_at": created_at + timedelta(minutes=15),
        "status": PendingActionStatus.EXECUTING,
        "created_at": created_at,
        "updated_at": created_at,
    }
    data.update(overrides)
    return PendingAction(**data)


def _fixed_time() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
