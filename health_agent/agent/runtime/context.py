"""Context Builder。

Context Builder 只组装当前任务必要上下文，不加载数据库、Redis、文件系统或完整
聊天历史。M2.5-B-3 只使用请求输入和 Mock 已知上下文，保证 INITIAL_PLANNING
行为不被额外上下文改变。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from agent.runtime.session import AgentSession


@dataclass(frozen=True)
class ContextSnapshot:
    """传给 Skill/Provider 的最小上下文快照。"""

    summary: str = ""
    facts: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    skill_payload: dict[str, Any] = field(default_factory=dict)


class ContextBuilder:
    """为 AgentLoop 构造最小上下文。"""

    def build(
        self,
        trigger: str,
        payload: Mapping[str, Any],
        session: AgentSession,
    ) -> ContextSnapshot:
        """基于请求输入构造上下文，不访问任何外部资源。"""
        payload_copy = dict(payload)
        user_text = str(payload_copy.get("userText") or payload_copy.get("user_text") or "").strip()
        summary = self._summary_for(trigger=trigger, user_text=user_text, session=session)
        return ContextSnapshot(
            summary=summary,
            facts={},
            candidates=[],
            skill_payload=payload_copy,
        )

    def _summary_for(self, trigger: str, user_text: str, session: AgentSession) -> str:
        """生成不会泄漏完整健康原文的简短上下文摘要。"""
        has_user_text = "yes" if user_text else "no"
        return (
            f"trigger={trigger}; session={session.session_id}; "
            f"hasUserText={has_user_text}; source=request_only"
        )
