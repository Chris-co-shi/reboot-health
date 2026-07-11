import multiprocessing
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from queue import Empty

from agent.models import ModelMessage, ModelResponse
from agent.runtime.execution_checkpoint import (
    RunExecutionCheckpoint,
    RunExecutionCheckpointPhase,
)
from agent.runtime.generic_loop import (
    ERROR_SESSION_RECOVERY_NOT_ELIGIBLE,
    GENERIC_STATUS_COMPLETED,
    GENERIC_STATUS_FAILED,
    GenericAgentLoop,
)
from agent.runtime.session import AgentSession, AgentSessionStatus
from agent.runtime.storage import JsonFileSessionStore
from tests.support.scripted_model_provider import ScriptedModelProvider


class StaleRecoveryMultiprocessTest(unittest.TestCase):
    """两个独立进程同时 recovery 同一个 stale Session 时只能一个成功。"""

    def test_concurrent_recovery_claim_allows_only_one_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            store.create(_stale_drive_ready_session())

            results = _run_two_workers(directory)
            statuses = sorted(result[0] for result in results)
            provider_calls = sum(int(result[2]) for result in results)
            stored = store.get("session-1")

            self.assertEqual(statuses, [GENERIC_STATUS_COMPLETED, GENERIC_STATUS_FAILED])
            self.assertEqual(provider_calls, 1)
            self.assertEqual(
                [result[1] for result in results if result[0] == GENERIC_STATUS_FAILED],
                [ERROR_SESSION_RECOVERY_NOT_ELIGIBLE],
            )
            self.assertEqual(stored.status, AgentSessionStatus.COMPLETED)
            self.assertEqual(stored.run_fence_generation, 2)
            self.assertIsNone(stored.active_run_id)
            self.assertIsNone(stored.execution_checkpoint)


def _run_two_workers(directory: str) -> list[tuple[str, str | None, int]]:
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    queue = context.Queue()
    processes = [
        context.Process(target=_recovery_worker, args=(directory, barrier, queue, label))
        for label in ("left", "right")
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
        raise AssertionError("stale recovery multiprocess test timed out")
    exitcodes = [process.exitcode for process in processes]
    if exitcodes != [0, 0]:
        raise AssertionError(f"worker exitcodes were {exitcodes!r}")

    results = [_queue_get(queue) for _ in processes]
    errors = [result for result in results if result[0] == "error"]
    if errors:
        raise AssertionError(f"worker errors were {errors!r}")
    return results


def _queue_get(queue) -> tuple[str, str | None, int]:
    try:
        return queue.get(timeout=2)
    except Empty as exc:
        raise AssertionError("worker did not report a result") from exc


def _recovery_worker(directory: str, barrier, queue, label: str) -> None:
    try:
        store = JsonFileSessionStore(directory, now_provider=_fixed_now)
        provider = ScriptedModelProvider(
            [ModelResponse(content=f"恢复完成 {label}", finish_reason="stop")]
        )
        loop = GenericAgentLoop(
            provider=provider,
            session_store=store,
            now_provider=_fixed_now,
            monotonic_provider=lambda: 100.0,
            run_lease_ttl_seconds=90,
            run_lease_heartbeat_interval_seconds=10,
            lease_safety_margin_seconds=1,
        )
        barrier.wait(5)
        result = loop.recover_stale_session("session-1")
        queue.put(
            (
                result.status,
                result.error.code if result.error is not None else None,
                len(provider.calls),
            )
        )
    except Exception as exc:  # pragma: no cover - 父进程只需要短异常摘要。
        queue.put(("error", type(exc).__name__, 0))


def _stale_drive_ready_session() -> AgentSession:
    heartbeat_at = _fixed_now() - timedelta(seconds=120)
    return AgentSession(
        session_id="session-1",
        status=AgentSessionStatus.RUNNING,
        messages=[ModelMessage(role="user", content="原始任务")],
        active_run_id="run-old",
        run_fence_generation=1,
        active_run_last_heartbeat_at=heartbeat_at,
        active_run_lease_expires_at=_fixed_now(),
        execution_checkpoint=RunExecutionCheckpoint(
            checkpoint_phase=RunExecutionCheckpointPhase.DRIVE_READY,
            originating_run_id="run-old",
            run_fence_generation=1,
            assistant_message_index=None,
            next_tool_call_index=0,
            current_tool_call_id=None,
            current_tool_name=None,
            model_turns_used=0,
            tool_calls_used=0,
            remaining_runtime_seconds=60,
            started_at=_fixed_now() - timedelta(seconds=30),
            deadline_at=_fixed_now() + timedelta(seconds=30),
            updated_at=heartbeat_at,
        ),
        created_at=heartbeat_at,
        updated_at=heartbeat_at,
    )


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
