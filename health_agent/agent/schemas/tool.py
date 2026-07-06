"""Tool Schema 预留模块。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolCallRequest:
    """一次受控 Tool 调用请求。"""

    name: str
    payload: dict[str, Any]
