"""Audit/Outbox SQLAlchemy 模型和原子领取实现。

所属层：Audit / Adapters。
职责：追加审计、Outbox 状态持久化、SKIP LOCKED 多 Pod 抢占与过期恢复。
边界：不执行远程副作用，不 commit，错误正文必须脱敏。
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, select, update
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from health_platform.modules.audit.domain.models import AuditEvent, OutboxEvent, OutboxStatus
from health_platform.platform.database.core import Base


class AuditEventRow(Base):
    """只追加审计事件数据库模型。"""

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_audit_events_user_time", "user_id", "occurred_at"),
        {"schema": "audit"},
    )
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    result: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(String(128))
    request_id: Mapped[str | None] = mapped_column(String(128))
    source_ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class OutboxEventRow(Base):
    """PostgreSQL 权威 Outbox 记录。"""

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_audit_outbox_claim", "status", "available_at", "next_attempt_at"),
        {"schema": "audit"},
    )
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(128))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))


class SqlAuditRepository:
    """追加 Audit/Outbox 的事务内 Repository。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: AuditEvent) -> None:
        """追加审计事件；Repository 不 commit，失败将回滚关键业务事务。"""
        self._session.add(
            AuditEventRow(
                event_id=event.event_id,
                occurred_at=event.occurred_at,
                actor_type=event.actor_type,
                actor_id=event.actor_id,
                user_id=event.user_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                result=event.result,
                reason=event.reason,
                trace_id=event.trace_id,
                request_id=event.request_id,
                source_ip=event.source_ip,
                user_agent=event.user_agent,
                event_metadata=event.metadata,
                previous_hash=event.previous_hash,
                event_hash=event.event_hash,
            )
        )

    def enqueue(self, event: OutboxEvent) -> None:
        """与业务数据同事务写入待发布副作用。"""
        self._session.add(
            OutboxEventRow(
                event_id=event.event_id,
                event_type=event.event_type,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                payload=event.payload,
                status=event.status.value,
                created_at=event.created_at,
                available_at=event.available_at,
                attempt_count=event.attempt_count,
                next_attempt_at=event.next_attempt_at,
            )
        )


class SqlOutboxRepository:
    """后台线程使用的原子 Outbox 领取和终态 Repository。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def recover_expired(self, now: datetime) -> int:
        """恢复锁租约过期的 PROCESSING，保证 Pod 崩溃后任务不会永久丢失。"""
        result = self._session.execute(
            update(OutboxEventRow)
            .where(
                OutboxEventRow.status == OutboxStatus.PROCESSING.value,
                OutboxEventRow.locked_until < now,
            )
            .values(status=OutboxStatus.PENDING.value, locked_by=None, locked_until=None)
        )
        return int(getattr(result, "rowcount", 0) or 0)

    def claim(self, worker_id: str, now: datetime, lock_seconds: int) -> OutboxEventRow | None:
        """用 FOR UPDATE SKIP LOCKED 让多个 Pod 并发领取但不互相阻塞或重复领取。"""
        row = self._session.execute(
            select(OutboxEventRow)
            .where(
                OutboxEventRow.status.in_([OutboxStatus.PENDING.value, OutboxStatus.FAILED.value]),
                OutboxEventRow.available_at <= now,
                (OutboxEventRow.next_attempt_at.is_(None))
                | (OutboxEventRow.next_attempt_at <= now),
            )
            .order_by(OutboxEventRow.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        row.status = OutboxStatus.PROCESSING.value
        row.locked_by = worker_id
        row.locked_until = now + timedelta(seconds=lock_seconds)
        row.attempt_count += 1
        return row

    def mark_published(self, event_id: UUID, now: datetime) -> None:
        """独立事务标记发布完成，幂等事件 ID 由下游去重。"""
        row = self._session.get(OutboxEventRow, event_id)
        if row is None:
            raise LookupError("outbox event not found")
        row.status = OutboxStatus.PUBLISHED.value
        row.published_at = now
        row.locked_by = None
        row.locked_until = None
        row.last_error = None

    def mark_failed(self, event_id: UUID, now: datetime, error: str, max_attempts: int = 8) -> None:
        """记录脱敏错误并指数退避；超过上限仍保留 FAILED 供告警和人工重放。"""
        row = self._session.get(OutboxEventRow, event_id)
        if row is None:
            raise LookupError("outbox event not found")
        row.status = OutboxStatus.FAILED.value
        row.last_error = error[:500]
        row.locked_by = None
        row.locked_until = None
        exponent = min(row.attempt_count, max_attempts)
        row.next_attempt_at = now + timedelta(seconds=min(2**exponent, 3600))
