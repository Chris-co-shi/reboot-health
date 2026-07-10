"""运行状态定义。

状态只用于描述 Python Runtime 内部进度，不代表已确认业务事实。
"""

from __future__ import annotations

from enum import StrEnum


class RunStatus(StrEnum):
    """AgentRun 的最小状态集合。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_CONFIRMATION = "waiting_confirmation"
