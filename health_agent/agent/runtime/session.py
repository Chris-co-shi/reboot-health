"""Session Runtime。

Session 只记录 Python Runtime 内部运行状态，不保存确认事实，也不替代后续
受控确认、持久化和审计边界。当前实现只提供内存存储，便于 AgentLoop 在一次
测试或本地运行中具备 Session 能力。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from agent.runtime.state import RunStatus


@dataclass
class AgentSession:
    """一次 Agent 交互会话的最小运行时状态。"""

    session_id: str
    status: RunStatus = RunStatus.PENDING
    current_skill: str | None = None
    turns: int = 0
    pending_confirmations: list[str] = field(default_factory=list)
    context_summary: str = ""
    locale: str = "zh-CN"


class InMemorySessionStore:
    """仅用于本地运行和测试的内存 SessionStore。"""

    def __init__(self) -> None:
        self._sessions: dict[str, AgentSession] = {}

    def create(self, session_id: str | None = None, locale: str = "zh-CN") -> AgentSession:
        """创建并保存一个新 session。"""
        session = AgentSession(session_id=session_id or f"session-{uuid4().hex}", locale=locale)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> AgentSession | None:
        """按 session_id 查找 session。"""
        return self._sessions.get(session_id)

    def get_or_create(
        self,
        session_id: str | None = None,
        locale: str = "zh-CN",
    ) -> AgentSession:
        """存在则返回现有 session，否则创建新 session。"""
        if session_id:
            existing = self.get(session_id)
            if existing is not None:
                return existing
        return self.create(session_id=session_id, locale=locale)
