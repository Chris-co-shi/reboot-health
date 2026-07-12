"""后台线程生命周期和异常可观察性测试。"""

import time

from health_platform.platform.background.worker import BackgroundWorker


def test_worker_is_non_daemon_and_stops_gracefully() -> None:
    worker = BackgroundWorker(lambda: False, 0.01)
    worker.start()
    time.sleep(0.02)
    assert worker.is_alive
    assert worker._thread is not None and not worker._thread.daemon
    worker.stop()
    assert not worker.is_alive


def test_worker_failure_is_observable() -> None:
    def fail() -> bool:
        raise RuntimeError("boom")

    worker = BackgroundWorker(fail, 0.01)
    worker.start()
    time.sleep(0.02)
    assert worker.last_error == "RuntimeError"
    assert not worker.is_alive
