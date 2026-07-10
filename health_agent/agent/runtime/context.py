"""Context Builder。

Context Builder 只组装当前任务必要上下文，不加载数据库、Redis、文件系统或完整
聊天历史。当前兼容阶段只使用请求输入和显式已知上下文，保证 INITIAL_PLANNING
行为不被额外上下文改变。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping

from agent.runtime.session import AgentSession


@dataclass(frozen=True)
class RuntimeEnvironment:
    """当前运行环境信息，不包含健康业务事实。"""

    current_date: str
    current_datetime: str
    timezone: str
    locale: str

    def to_provider_payload(self) -> dict[str, str]:
        """转成传给 Skill/Provider 的稳定字段名。"""
        return {
            "currentDate": self.current_date,
            "currentDateTime": self.current_datetime,
            "timezone": self.timezone,
            "locale": self.locale,
        }


@dataclass(frozen=True)
class ContextSnapshot:
    """传给 Skill/Provider 的最小上下文快照。"""

    summary: str = ""
    facts: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    skill_payload: dict[str, Any] = field(default_factory=dict)
    runtime_environment: RuntimeEnvironment | None = None


class ContextBuilder:
    """为 AgentLoop 构造最小上下文。"""

    def __init__(
        self,
        now_provider: Callable[[], datetime] | None = None,
        locale: str = "zh-CN",
    ) -> None:
        self._now_provider = now_provider
        self.locale = locale

    def build(
        self,
        trigger: str,
        payload: Mapping[str, Any],
        session: AgentSession,
    ) -> ContextSnapshot:
        """基于请求输入构造上下文，不访问任何外部资源。"""
        payload_copy = dict(payload)
        user_text = str(payload_copy.get("userText") or payload_copy.get("user_text") or "").strip()
        locale = str(payload_copy.get("locale") or session.locale or self.locale)
        runtime_environment = build_runtime_environment(
            now=self._now_provider() if self._now_provider else None,
            locale=locale,
        )
        payload_copy["today"] = runtime_environment.current_date
        payload_copy["runtimeEnvironment"] = runtime_environment.to_provider_payload()
        summary = self._summary_for(trigger=trigger, user_text=user_text, session=session)
        return ContextSnapshot(
            summary=summary,
            facts={},
            candidates=[],
            skill_payload=payload_copy,
            runtime_environment=runtime_environment,
        )

    def _summary_for(self, trigger: str, user_text: str, session: AgentSession) -> str:
        """生成不会泄漏完整健康原文的简短上下文摘要。"""
        has_user_text = "yes" if user_text else "no"
        return (
            f"trigger={trigger}; session={session.session_id}; "
            f"hasUserText={has_user_text}; source=request_only"
        )


def build_runtime_environment(
    now: datetime | None = None,
    locale: str = "zh-CN",
) -> RuntimeEnvironment:
    """构建通用运行环境；默认使用当前进程本地时区。"""
    if now is None:
        current = datetime.now().astimezone()
    elif now.tzinfo is None or now.utcoffset() is None:
        current = now.astimezone()
    else:
        current = now
    return RuntimeEnvironment(
        current_date=current.date().isoformat(),
        current_datetime=current.isoformat(),
        timezone=_utc_offset(current),
        locale=locale,
    )


def _utc_offset(value: datetime) -> str:
    """返回 ISO 风格 UTC offset，例如 +09:00。"""
    offset = value.utcoffset()
    if offset is None:
        return "+00:00"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"
