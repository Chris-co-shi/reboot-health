import multiprocessing
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from queue import Empty

from agent.runtime.pending_action import PendingAction
from agent.runtime.pending_action_store import (
    PendingActionAlreadyExistsError,
    PendingActionVersionConflictError,
)
from agent.runtime.session import (
    AgentSession,
    SessionAlreadyExistsError,
    SessionVersionConflictError,
)
from agent.runtime.storage import JsonFilePendingActionStore, JsonFileSessionStore


class JsonStoreMultiprocessTest(unittest.TestCase):
    """用真实子进程验证 JSON Store 的文件锁和磁盘 CAS。

    这些测试不依赖线程锁：每个 worker 都重新创建 Store 实例，只有 `.lock` 文件和
    JSON 文件 version 能协调并发写入。预期结果是“一个成功，一个明确失败”，不能
    出现静默覆盖或损坏 JSON。
    """

    def test_concurrent_session_create_allows_only_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = _run_two_workers(
                _session_create_worker,
                directory,
                "left",
                "right",
            )
            statuses = sorted(result[0] for result in results)
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)

            self.assertEqual(statuses, ["created", "exists"])
            self.assertEqual(store.get("session-1").session_id, "session-1")

    def test_concurrent_session_save_uses_disk_version_cas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFileSessionStore(directory, now_provider=_fixed_now)
            store.create(_session())

            results = _run_two_workers(
                _session_save_worker,
                directory,
                "left",
                "right",
            )
            statuses = sorted(result[0] for result in results)
            saved_labels = [result[1] for result in results if result[0] == "saved"]
            loaded = store.get("session-1")

            self.assertEqual(statuses, ["conflict", "saved"])
            self.assertEqual(loaded.version, 1)
            self.assertEqual(loaded.context_summary, saved_labels[0])

    def test_concurrent_pending_action_create_allows_only_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results = _run_two_workers(
                _pending_action_create_worker,
                directory,
                "left",
                "right",
            )
            statuses = sorted(result[0] for result in results)
            store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)

            self.assertEqual(statuses, ["created", "exists"])
            self.assertEqual(store.get("action-1").action_id, "action-1")

    def test_concurrent_pending_action_save_uses_disk_version_cas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
            store.create(_pending_action())

            results = _run_two_workers(
                _pending_action_save_worker,
                directory,
                "left",
                "right",
            )
            statuses = sorted(result[0] for result in results)
            saved_labels = [result[1] for result in results if result[0] == "saved"]
            loaded = store.get("action-1")

            self.assertEqual(statuses, ["conflict", "saved"])
            self.assertEqual(loaded.version, 1)
            self.assertEqual(loaded.summary, saved_labels[0])


def _run_two_workers(
    worker,
    directory: str | Path,
    first_label: str,
    second_label: str,
) -> list[tuple[str, ...]]:
    """启动两个 spawn 子进程，并收集每个 worker 的单行状态结果。"""

    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    queue = context.Queue()
    processes = [
        context.Process(
            target=worker,
            args=(str(directory), barrier, queue, label),
        )
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
        raise AssertionError("multiprocess JSON store test timed out")

    exitcodes = [process.exitcode for process in processes]
    if exitcodes != [0, 0]:
        raise AssertionError(f"worker exitcodes were {exitcodes!r}")

    results = [_queue_get(queue) for _ in processes]
    errors = [result for result in results if result[0] == "error"]
    if errors:
        raise AssertionError(f"worker errors were {errors!r}")
    return results


def _queue_get(queue) -> tuple[str, ...]:
    """从 multiprocessing Queue 读取结果，并把超时转成断言失败。"""

    try:
        return queue.get(timeout=2)
    except Empty as exc:
        raise AssertionError("worker did not report a result") from exc


def _session_create_worker(
    directory: str,
    barrier,
    queue,
    label: str,
) -> None:
    """并发 create 同一个 session_id，验证文件锁内的 exists 检查。"""

    try:
        store = JsonFileSessionStore(directory, now_provider=_fixed_now)
        barrier.wait(5)
        store.create(_session(context_summary=label))
        queue.put(("created", label))
    except SessionAlreadyExistsError:
        queue.put(("exists", label))
    except Exception as exc:  # pragma: no cover - 失败时只回传异常类型供父进程断言。
        queue.put(("error", type(exc).__name__))


def _session_save_worker(
    directory: str,
    barrier,
    queue,
    label: str,
) -> None:
    """两个进程读取同一旧版本后同时 save，验证磁盘 version CAS。"""

    try:
        store = JsonFileSessionStore(directory, now_provider=_later_now)
        session = store.get("session-1")
        session.context_summary = label
        expected_version = session.version
        barrier.wait(5)
        store.save(session, expected_version=expected_version)
        queue.put(("saved", label))
    except SessionVersionConflictError:
        queue.put(("conflict", label))
    except Exception as exc:  # pragma: no cover - 失败时只回传异常类型供父进程断言。
        queue.put(("error", type(exc).__name__))


def _pending_action_create_worker(
    directory: str,
    barrier,
    queue,
    label: str,
) -> None:
    """并发 create 同一个 action_id，验证 PendingAction 不会被覆盖。"""

    try:
        store = JsonFilePendingActionStore(directory, now_provider=_fixed_now)
        barrier.wait(5)
        store.create(_pending_action(summary=label))
        queue.put(("created", label))
    except PendingActionAlreadyExistsError:
        queue.put(("exists", label))
    except Exception as exc:  # pragma: no cover - 失败时只回传异常类型供父进程断言。
        queue.put(("error", type(exc).__name__))


def _pending_action_save_worker(
    directory: str,
    barrier,
    queue,
    label: str,
) -> None:
    """两个进程读取同一旧版本后同时 save，验证 PendingAction CAS。"""

    try:
        store = JsonFilePendingActionStore(directory, now_provider=_later_now)
        action = store.get("action-1")
        action = replace(action, summary=label)
        expected_version = action.version
        barrier.wait(5)
        store.save(action, expected_version=expected_version)
        queue.put(("saved", label))
    except PendingActionVersionConflictError:
        queue.put(("conflict", label))
    except Exception as exc:  # pragma: no cover - 失败时只回传异常类型供父进程断言。
        queue.put(("error", type(exc).__name__))


def _session(*, context_summary: str = "seed") -> AgentSession:
    """构造可被并发 worker 复用的 Session 快照。"""

    return AgentSession(
        session_id="session-1",
        created_at=_fixed_now(),
        updated_at=_fixed_now(),
        context_summary=context_summary,
    )


def _pending_action(*, summary: str = "seed") -> PendingAction:
    """构造可被并发 worker 复用的 PendingAction 快照。"""

    created_at = _fixed_now()
    return PendingAction(
        action_id="action-1",
        session_id="session-1",
        originating_run_id="run-1",
        tool_call_id="call-1",
        tool_name="record_weight_measurement",
        arguments={"value": 95, "unit": "kg"},
        assistant_message_index=2,
        tool_call_index=0,
        summary=summary,
        created_at=created_at,
        updated_at=created_at,
        expires_at=created_at + timedelta(minutes=15),
    )


def _fixed_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _later_now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 6, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
