"""Agent Run ownership 与 fencing 合同。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunOwnership:
    """当前 RUNNING Session 的最小 ownership 快照。

    该对象只在 Runtime 内部传递，不进入公开 AgentRunResult，也不携带 Store、
    Provider、Executor 或可变 Session 对象。fence_generation 用于阻断旧 owner
    在 stale recovery 后继续写入。
    """

    session_id: str
    run_id: str
    fence_generation: int

    def __post_init__(self) -> None:
        session_id = str(self.session_id or "").strip()
        if not session_id:
            raise ValueError("session_id must not be empty")
        object.__setattr__(self, "session_id", session_id)

        run_id = str(self.run_id or "").strip()
        if not run_id:
            raise ValueError("run_id must not be empty")
        object.__setattr__(self, "run_id", run_id)

        if not isinstance(self.fence_generation, int) or self.fence_generation <= 0:
            raise ValueError("fence_generation must be a positive integer")
