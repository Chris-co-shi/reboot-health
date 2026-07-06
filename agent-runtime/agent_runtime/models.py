"""结构化输入输出模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecuteRequest:
    """Java 提交给 Python Runtime 的运行请求。"""

    run_id: str
    user_id: str
    device_id: str
    trigger_type: str
    input_summary: str
    mock_mode: str | None = None

    @staticmethod
    def from_json(data: dict[str, Any]) -> "ExecuteRequest":
        return ExecuteRequest(
            run_id=str(data["runId"]),
            user_id=str(data["userId"]),
            device_id=str(data["deviceId"]),
            trigger_type=str(data["triggerType"]),
            input_summary=str(data["inputSummary"]),
            mock_mode=(None if data.get("mockMode") is None else str(data.get("mockMode"))),
        )


@dataclass(frozen=True)
class AgentCard:
    """用户可见的结构化卡片。"""

    type: str
    title: str
    content: str

    def to_json(self) -> dict[str, str]:
        return {"type": self.type, "title": self.title, "content": self.content}


@dataclass(frozen=True)
class ExecuteResponse:
    """Runtime 返回给 Java 的结构化结果。"""

    schema_version: str
    message: str
    cards: list[AgentCard]

    def to_json(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "message": self.message,
            "cards": [card.to_json() for card in self.cards],
        }
