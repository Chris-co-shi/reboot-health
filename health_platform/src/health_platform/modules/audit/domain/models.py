"""Audit 与 Outbox 领域模型。

所属层：Audit / Domain。
职责：追加审计哈希链和可靠副作用状态。
边界：不发送远程请求，不包含 Token、密码、MFA 或完整健康原文。
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class OutboxStatus(StrEnum):
    """平台 Outbox 处理状态。"""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class AuditEvent:
    """只追加审计事件；event_hash 绑定前序哈希和规范化内容。"""

    actor_type: str
    action: str
    resource_type: str
    result: str
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    actor_id: UUID | None = None
    user_id: UUID | None = None
    resource_id: UUID | None = None
    reason: str | None = None
    trace_id: str | None = None
    request_id: str | None = None
    source_ip: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    previous_hash: str = "GENESIS"

    @property
    def event_hash(self) -> str:
        """计算稳定哈希链摘要，用于检测删除、重排和内容篡改。"""
        canonical = json.dumps(
            {
                "event_id": str(self.event_id),
                "occurred_at": self.occurred_at.isoformat(),
                "actor_type": self.actor_type,
                "actor_id": str(self.actor_id) if self.actor_id else None,
                "user_id": str(self.user_id) if self.user_id else None,
                "action": self.action,
                "resource_type": self.resource_type,
                "resource_id": str(self.resource_id) if self.resource_id else None,
                "result": self.result,
                "reason": self.reason,
                "trace_id": self.trace_id,
                "request_id": self.request_id,
                "metadata": self.metadata,
                "previous_hash": self.previous_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class OutboxEvent:
    """可靠异步副作用记录；远程执行必须发生在业务事务提交后。"""

    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    payload: dict[str, Any]
    event_id: UUID = field(default_factory=uuid4)
    status: OutboxStatus = OutboxStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    available_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    attempt_count: int = 0
    next_attempt_at: datetime | None = None
    locked_by: str | None = None
    locked_until: datetime | None = None
    published_at: datetime | None = None
    last_error: str | None = None
