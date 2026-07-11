import multiprocessing
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from queue import Empty

from agent.runtime.session import (
    AgentSession,
    AgentSessionStatus,
    SessionVersionConflictError,
)
from agent.runtime.storage import JsonFileSessionStore


class RunLeaseMultiprocessTest(unittest.TestCase):
    """用独立子进程验证 lease claim/heartbeat 仍依赖磁盘 CAS。"""

    def test_concurrent_claim_allows_only_one_owner_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            store.create(
                AgentSession(
                    session_id="session-1",
                    created_at=_fixed_now(),
                    updated_at=_fixed_now(),
                )
            )

            results = _run_two_workers(_claim_worker, directory, "left", "right")
            statuses = sorted(result[0] for result in results)
            stored = store.get("session-1")

            self.assertEqual(statuses, ["claimed", "conflict"])
            self.assertEqual(stored.status, AgentSessionStatus.RUNNING)
            self.assertEqual(stored.run_fence_generation, 1)
            self.assertIn(stored.active_run_id, {"run-left", "run-right"})
            self.assertEqual(stored.version, 1)

    def test_concurrent_heartbeat_allows_only_one_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            store.create(
                _running_session(
                    heartbeat_at=_fixed_now(),
                    lease_expires_at=_fixed_now() + timedelta(seconds=60),
                )
            )

            results = _run_two_workers(_heartbeat_worker, directory, "left", "right")
            statuses = sorted(result[0] for result in results)
            stored = store.get("session-1")

            self.assertEqual(statuses, ["conflict", "heartbeat"])
            self.assertEqual(stored.version, 1)
            self.assertEqual(stored.active_run_last_heartbeat_at, _later_now())
            self.assertEqual(
                stored.active_run_lease_expires_at,
                _later_now() + timedelta(seconds=60),
            )


def _run_two_workers(worker, directory: str | Path, first_label: str, second_label: str):
    """启动两个 spawn 子进程；每个 worker 必须在 10 秒内完成。"""

    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    queue = context.Queue()
    processes = [
        context.Process(target=worker, args=(str(directory), barrier, queue, label))
        for label in (first_label, second_label)
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
        raise AssertionError("run lease multiprocess test timed out")

    exitcodes = [process.exitcode for process in processes]
    if exitcodes != [0, 0]:
        raise AssertionError(f"worker exitcodes were {exitcodes!r}")

    results = [_queue_get(queue) for _ in processes]
    errors = [result for result in results if result[0] == "error"]
    if errors:
        raise AssertionError(f"worker errors were {errors!r}")
    return results


def _queue_get(queue) -> tuple[str, ...]:
    try:
        return queue.get(timeout=2)
    except Empty as exc:
        raise AssertionError("worker did not report a result") from exc


def _claim_worker(directory: str, barrier, queue, label: str) -> None:
    """两个进程从同一 ACTIVE version 竞争 RUNNING claim。"""

    try:
        store = JsonFileSessionStore(directory, now_provider=_fixed_now)
        session = store.get("session-1")
        claimed = replace(
            session,
            status=AgentSessionStatus.RUNNING,
            active_run_id=f"run-{label}",
            run_fence_generation=session.run_fence_generation + 1,
            active_run_last_heartbeat_at=_fixed_now(),
            active_run_lease_expires_at=_fixed_now() + timedelta(seconds=60),
        )
        barrier.wait(5)
        store.save(claimed, expected_version=session.version)
        queue.put(("claimed", label))
    except SessionVersionConflictError:
        queue.put(("conflict", label))
    except Exception as exc:  # pragma: no cover - 父进程只需要短异常摘要。
        queue.put(("error", type(exc).__name__, str(exc)))


def _heartbeat_worker(directory: str, barrier, queue, label: str) -> None:
    """两个进程从同一 RUNNING version 竞争 heartbeat 写入。"""

    try:
        store = JsonFileSessionStore(directory, now_provider=_later_now)
        session = store.get("session-1")
        refreshed = replace(
            session,
            active_run_last_heartbeat_at=_later_now(),
            active_run_lease_expires_at=_later_now() + timedelta(seconds=60),
        )
        barrier.wait(5)
        store.save(refreshed, expected_version=session.version)
        queue.put(("heartbeat", label))
    except SessionVersionConflictError:
        queue.put(("conflict", label))
    except Exception as exc:  # pragma: no cover - 父进程只需要短异常摘要。
        queue.put(("error", type(exc).__name__, str(exc)))


def _running_session(
    *,
    heartbeat_at: datetime,
    lease_expires_at: datetime,
) -> AgentSession:
    return AgentSession(
        session_id="session-1",
        status=AgentSessionStatus.RUNNING,
        active_run_id="run-1",
        run_fence_generation=1,
        active_run_last_heartbeat_at=heartbeat_at,
        active_run_lease_expires_at=lease_expires_at,
        created_at=_fixed_now(),
        updated_at=_fixed_now(),
    )


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _later_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 6, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
