import multiprocessing
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from queue import Empty

from agent.runtime.orphan_actions import (
    OrphanPendingActionClassification,
    cleanup_orphan_pending_actions,
    scan_orphan_pending_actions,
)
from agent.runtime.pending_action import (
    PendingAction,
    PendingActionStatus,
    transition_pending_action,
)
from agent.runtime.pending_action_store import (
    InMemoryPendingActionStore,
    PendingActionVersionConflictError,
)
from agent.runtime.session import AgentSession, AgentSessionStatus, InMemorySessionStore
from agent.runtime.storage import JsonFilePendingActionStore, JsonFileSessionStore
from agent.tools.contract import success_content


class OrphanPendingActionsTest(unittest.TestCase):
    """PendingAction orphan 分类与安全维护规则。"""

    def test_scan_classifies_reference_and_orphan_shapes(self) -> None:
        sessions = InMemorySessionStore()
        actions = InMemoryPendingActionStore()
        sessions.create(
            AgentSession(
                session_id="session-referenced",
                status=AgentSessionStatus.WAITING_CONFIRMATION,
                pending_action_id="referenced",
            )
        )
        sessions.create(AgentSession(session_id="session-mismatch"))
        for action in (
            _action("referenced", session_id="session-referenced"),
            _action("unreferenced"),
            _action("expired", expires_at=_fixed_now() - timedelta(seconds=1)),
            _action("mismatch", session_id="session-mismatch"),
            _approved_action("approved"),
            _executing_action("executing"),
            _terminal_action("terminal"),
        ):
            actions.create(action)

        reports = {
            report.action_id: report
            for report in scan_orphan_pending_actions(
                session_store=sessions,
                pending_action_store=actions,
                now=_fixed_now(),
            )
        }

        self.assertEqual(
            reports["referenced"].classification,
            OrphanPendingActionClassification.REFERENCED_PENDING,
        )
        self.assertTrue(reports["referenced"].referenced)
        self.assertEqual(
            reports["unreferenced"].classification,
            OrphanPendingActionClassification.UNREFERENCED_PENDING,
        )
        self.assertEqual(
            reports["expired"].classification,
            OrphanPendingActionClassification.EXPIRED_PENDING,
        )
        self.assertEqual(
            reports["mismatch"].classification,
            OrphanPendingActionClassification.SESSION_REFERENCE_MISMATCH,
        )
        self.assertEqual(
            reports["approved"].classification,
            OrphanPendingActionClassification.ORPHAN_APPROVED,
        )
        self.assertEqual(
            reports["executing"].classification,
            OrphanPendingActionClassification.ORPHAN_EXECUTING,
        )
        self.assertEqual(
            reports["terminal"].classification,
            OrphanPendingActionClassification.ORPHAN_TERMINAL,
        )

    def test_cleanup_dry_run_does_not_modify_store(self) -> None:
        sessions = InMemorySessionStore()
        actions = InMemoryPendingActionStore()
        actions.create(_action("expired", expires_at=_fixed_now() - timedelta(seconds=1)))

        result = cleanup_orphan_pending_actions(
            session_store=sessions,
            pending_action_store=actions,
            now=_fixed_now(),
            dry_run=True,
        )

        self.assertTrue(result.dry_run)
        self.assertEqual(result.expired_action_ids, ())
        self.assertEqual(actions.get("expired").status, PendingActionStatus.PENDING)

    def test_cleanup_expires_only_unreferenced_expired_pending(self) -> None:
        sessions = InMemorySessionStore()
        actions = InMemoryPendingActionStore()
        actions.create(_action("expired", expires_at=_fixed_now() - timedelta(seconds=1)))
        actions.create(_action("unexpired", expires_at=_fixed_now() + timedelta(seconds=60)))
        actions.create(_approved_action("approved"))
        actions.create(_executing_action("executing"))

        result = cleanup_orphan_pending_actions(
            session_store=sessions,
            pending_action_store=actions,
            now=_fixed_now(),
            dry_run=False,
        )

        self.assertEqual(result.expired_action_ids, ("expired",))
        self.assertEqual(actions.get("expired").status, PendingActionStatus.EXPIRED)
        self.assertEqual(actions.get("unexpired").status, PendingActionStatus.PENDING)
        self.assertEqual(actions.get("approved").status, PendingActionStatus.APPROVED)
        self.assertEqual(actions.get("executing").status, PendingActionStatus.EXECUTING)

    def test_cleanup_deletes_only_old_unreferenced_terminal_actions(self) -> None:
        sessions = InMemorySessionStore()
        actions = InMemoryPendingActionStore()
        sessions.create(
            AgentSession(
                session_id="session-referenced",
                status=AgentSessionStatus.WAITING_CONFIRMATION,
                pending_action_id="referenced-terminal",
            )
        )
        actions.create(_terminal_action("old-terminal", resolved_at=_fixed_now() - timedelta(days=2)))
        actions.create(_terminal_action("new-terminal", resolved_at=_fixed_now()))
        actions.create(
            _terminal_action(
                "referenced-terminal",
                session_id="session-referenced",
                resolved_at=_fixed_now() - timedelta(days=2),
            )
        )

        result = cleanup_orphan_pending_actions(
            session_store=sessions,
            pending_action_store=actions,
            now=_fixed_now(),
            dry_run=False,
            terminal_retention_seconds=24 * 60 * 60,
        )

        self.assertEqual(result.deleted_action_ids, ("old-terminal",))
        self.assertIsNone(actions.get("old-terminal"))
        self.assertIsNotNone(actions.get("new-terminal"))
        self.assertIsNotNone(actions.get("referenced-terminal"))

    def test_cleanup_reports_cas_conflicts_without_stopping_other_actions(self) -> None:
        sessions = InMemorySessionStore()
        actions = ConflictPendingActionStore(conflict_on_save={"expired-conflict"})
        actions.create(_action("expired-conflict", expires_at=_fixed_now() - timedelta(seconds=1)))
        actions.create(_action("expired-ok", expires_at=_fixed_now() - timedelta(seconds=1)))

        result = cleanup_orphan_pending_actions(
            session_store=sessions,
            pending_action_store=actions,
            now=_fixed_now(),
            dry_run=False,
        )

        self.assertEqual(result.expired_action_ids, ("expired-ok",))
        self.assertEqual(result.conflicted_action_ids, ("expired-conflict",))
        self.assertEqual(actions.get("expired-conflict").status, PendingActionStatus.PENDING)
        self.assertEqual(actions.get("expired-ok").status, PendingActionStatus.EXPIRED)

    def test_json_store_scan_and_cleanup_delete_terminal_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sessions = JsonFileSessionStore(directory, now_provider=_fixed_now)
            actions = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
            actions.create(_terminal_action("old-terminal", resolved_at=_fixed_now() - timedelta(days=2)))

            result = cleanup_orphan_pending_actions(
                session_store=sessions,
                pending_action_store=actions,
                now=_fixed_now(),
                dry_run=False,
                terminal_retention_seconds=24 * 60 * 60,
            )

            self.assertEqual(result.deleted_action_ids, ("old-terminal",))
            self.assertIsNone(actions.get("old-terminal"))

    def test_multiprocess_terminal_delete_allows_only_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            actions = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
            actions.create(_terminal_action("old-terminal", resolved_at=_fixed_now() - timedelta(days=2)))

            results = _run_two_delete_workers(directory)

            self.assertEqual(sorted(results), ["conflict", "deleted"])
            self.assertIsNone(actions.get("old-terminal"))


class ConflictPendingActionStore(InMemoryPendingActionStore):
    def __init__(self, *, conflict_on_save: set[str] | None = None) -> None:
        super().__init__()
        self.conflict_on_save = set(conflict_on_save or set())

    def save(self, action: PendingAction, expected_version: int) -> PendingAction:
        if action.action_id in self.conflict_on_save:
            raise PendingActionVersionConflictError("forced conflict")
        return super().save(action, expected_version)


def _run_two_delete_workers(directory: str) -> list[str]:
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    queue = context.Queue()
    processes = [
        context.Process(target=_delete_worker, args=(directory, barrier, queue))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)

    alive = [process for process in processes if process.is_alive()]
    if alive:
        for process in alive:
            process.terminate()
        for process in alive:
            process.join(2)
        raise AssertionError("orphan cleanup multiprocess test timed out")
    exitcodes = [process.exitcode for process in processes]
    if exitcodes != [0, 0]:
        raise AssertionError(f"worker exitcodes were {exitcodes!r}")
    results = [_queue_get(queue) for _ in processes]
    errors = [result for result in results if result.startswith("error:")]
    if errors:
        raise AssertionError(f"worker errors were {errors!r}")
    return results


def _delete_worker(directory: str, barrier, queue) -> None:
    try:
        store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
        action = store.get("old-terminal")
        barrier.wait(5)
        try:
            store.delete("old-terminal", expected_version=action.version)
            queue.put("deleted")
        except Exception:
            queue.put("conflict")
    except Exception as exc:  # pragma: no cover - 父进程只需要短异常摘要。
        queue.put(f"error:{type(exc).__name__}")


def _queue_get(queue) -> str:
    try:
        return queue.get(timeout=2)
    except Empty as exc:
        raise AssertionError("worker did not report a result") from exc


def _action(
    action_id: str,
    *,
    session_id: str = "missing-session",
    expires_at: datetime | None = None,
    created_at: datetime | None = None,
) -> PendingAction:
    created_at = created_at or _fixed_now() - timedelta(hours=1)
    return PendingAction(
        action_id=action_id,
        session_id=session_id,
        originating_run_id="run-1",
        tool_call_id=f"call-{action_id}",
        tool_name="record_metric",
        arguments={"value": 1},
        assistant_message_index=2,
        tool_call_index=0,
        summary="Record metric",
        created_at=created_at,
        updated_at=created_at,
        expires_at=expires_at or _fixed_now() + timedelta(minutes=15),
    )


def _approved_action(action_id: str) -> PendingAction:
    return transition_pending_action(
        _action(action_id),
        PendingActionStatus.APPROVED,
        now=_fixed_now() - timedelta(minutes=30),
    )


def _executing_action(action_id: str) -> PendingAction:
    return transition_pending_action(
        _approved_action(action_id),
        PendingActionStatus.EXECUTING,
        now=_fixed_now() - timedelta(minutes=20),
    )


def _terminal_action(
    action_id: str,
    *,
    session_id: str = "missing-session",
    resolved_at: datetime | None = None,
) -> PendingAction:
    approved = transition_pending_action(
        _action(
            action_id,
            session_id=session_id,
            created_at=(resolved_at or _fixed_now()) - timedelta(hours=1),
            expires_at=(resolved_at or _fixed_now()) - timedelta(minutes=30),
        ),
        PendingActionStatus.APPROVED,
        now=(resolved_at or _fixed_now()) - timedelta(minutes=2),
    )
    executing = transition_pending_action(
        approved,
        PendingActionStatus.EXECUTING,
        now=(resolved_at or _fixed_now()) - timedelta(minutes=1),
    )
    return transition_pending_action(
        executing,
        PendingActionStatus.EXECUTED,
        now=resolved_at or _fixed_now(),
        result_content=success_content({"ok": True}),
    )


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
