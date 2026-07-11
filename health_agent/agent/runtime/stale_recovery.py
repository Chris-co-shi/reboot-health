"""Stale RUNNING Session recovery 的内部分类合同。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StaleRecoveryClassification(StrEnum):
    """Recovery 对 stale RUNNING session 的安全分类。"""

    NOT_ELIGIBLE = "not_eligible"
    SAFE_RESUME = "safe_resume"
    MODEL_STATE_UNKNOWN = "model_state_unknown"
    TOOL_STATE_UNKNOWN = "tool_state_unknown"
    FINALIZATION_STATE_UNKNOWN = "finalization_state_unknown"
    CHECKPOINT_CORRUPTED = "checkpoint_corrupted"


@dataclass(frozen=True)
class StaleSessionInspection:
    """不含 active_run_id、消息正文或 Tool arguments 的 recovery 检查摘要。"""

    session_id: str
    classification: StaleRecoveryClassification
    checkpoint_phase: str | None = None

    def __post_init__(self) -> None:
        session_id = str(self.session_id or "").strip()
        if not session_id:
            raise ValueError("session_id must not be empty")
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(
            self,
            "classification",
            StaleRecoveryClassification(self.classification),
        )
        checkpoint_phase = (
            str(self.checkpoint_phase or "").strip()
            if self.checkpoint_phase is not None
            else None
        )
        object.__setattr__(self, "checkpoint_phase", checkpoint_phase or None)
