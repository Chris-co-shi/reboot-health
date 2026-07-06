"""Agent Runtime 通用 Schema。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AgentRequest:
    """AgentCore 可处理的请求对象。"""

    trigger: str
    input: dict[str, Any]
