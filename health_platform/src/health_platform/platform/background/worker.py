"""可停止、可观察的后台线程。

所属层：Platform / Background。
职责：周期领取 Outbox、事务外处理副作用、维护 heartbeat 和优雅退出。
边界：线程不是 daemon；每次数据库操作使用独立 Session；异常不得静默死亡。
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """lifespan 管理的后台 Worker；readiness 可依据 alive/heartbeat 判断健康。"""

    def __init__(self, poll_once: Callable[[], bool], poll_seconds: float = 1.0) -> None:
        self._poll_once = poll_once
        self._poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_heartbeat: datetime | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        """启动非 daemon 线程；重复启动保持幂等。"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="health-platform-outbox", daemon=False
        )
        self._thread.start()

    def stop(self, timeout: float = 15.0) -> None:
        """停止领取新任务并等待当前短任务；超时由部署层安全终止进程。"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout)

    @property
    def is_alive(self) -> bool:
        """返回真实线程存活状态供 readiness 判断。"""
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                self.last_heartbeat = datetime.now(UTC)
                processed = self._poll_once()
                if not processed:
                    self._stop_event.wait(self._poll_seconds)
        except Exception as exc:
            self.last_error = type(exc).__name__
            logger.exception("background_worker_failed")
