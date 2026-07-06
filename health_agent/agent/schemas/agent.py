"""Agent Runtime 通用 Schema 与合同常量。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


AGENT_RUN_SCHEMA_VERSION = "health-agent.run.v0"

AGENT_RUN_STATUS_COMPLETED = "completed"
AGENT_RUN_STATUS_FAILED = "failed"
AGENT_RUN_STATUS_UNSUPPORTED = "unsupported"
AGENT_RUN_STATUS_ERROR = "error"
AGENT_RUN_STATUS_WAITING_CONFIRMATION = "waiting_confirmation"

FINAL_OUTCOME_COMPLETED = "completed"
FINAL_OUTCOME_FAILED = "failed"
FINAL_OUTCOME_UNSUPPORTED = "unsupported"
FINAL_OUTCOME_ERROR = "error"
FINAL_OUTCOME_MAX_STEPS_EXCEEDED = "max_steps_exceeded"
FINAL_OUTCOME_WAITING_CONFIRMATION = "waiting_confirmation"


@dataclass(frozen=True)
class AgentRequest:
    """AgentCore 可处理的请求对象。"""

    trigger: str
    input: dict[str, Any]
