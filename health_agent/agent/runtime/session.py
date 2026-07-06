"""Session Runtime 预留模块。

Session 后续负责区分 Conversation、Session、AgentRun、ToolCall 和 Confirmation。
当前阶段只保留最小标识模型，不承诺持久化能力。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSession:
    """一次 Agent 交互会话的最小标识。"""

    session_id: str
    locale: str = "zh-CN"
