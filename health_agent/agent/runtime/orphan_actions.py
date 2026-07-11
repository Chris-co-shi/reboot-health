"""PendingAction orphan 检测与维护工具。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from agent.runtime.pending_action import (
    PendingAction,
    PendingActionStatus,
    transition_pending_action,
    utc_now,
)
from agent.runtime.pending_action_store import (
    PendingActionNotFoundError,
    PendingActionStore,
    PendingActionVersionConflictError,
)
from agent.runtime.session import AgentSession, AgentSessionStatus, SessionStore


class OrphanPendingActionClassification(StrEnum):
    """PendingAction 与 Session 引用关系的维护分类。"""

    REFERENCED_PENDING = "referenced_pending"
    UNREFERENCED_PENDING = "unreferenced_pending"
    EXPIRED_PENDING = "expired_pending"
    ORPHAN_APPROVED = "orphan_approved"
    ORPHAN_EXECUTING = "orphan_executing"
    ORPHAN_TERMINAL = "orphan_terminal"
    SESSION_REFERENCE_MISMATCH = "session_reference_mismatch"


TERMINAL_PENDING_ACTION_STATUSES = {
    PendingActionStatus.REJECTED,
    PendingActionStatus.EXECUTED,
    PendingActionStatus.FAILED,
    PendingActionStatus.EXPIRED,
}


class PendingActionMaintenanceStore(PendingActionStore, Protocol):
    """维护专用 PendingAction Store 合同。"""

    def list_all(self) -> list[PendingAction]:
        """列出全部 PendingAction 快照。"""
        ...

    def delete(self, action_id: str, expected_version: int) -> None:
        """按 expected_version 删除 PendingAction。"""
        ...


@dataclass(frozen=True)
class OrphanPendingActionReport:
    """不包含 arguments/result_content 的 PendingAction 维护摘要。"""

    action_id: str
    session_id: str
    status: PendingActionStatus
    classification: OrphanPendingActionClassification
    referenced: bool
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    resolved_at: datetime | None


@dataclass(frozen=True)
class OrphanPendingActionMaintenanceResult:
    """一次 orphan scan/cleanup 的汇总。"""

    reports: tuple[OrphanPendingActionReport, ...]
    expired_action_ids: tuple[str, ...] = ()
    deleted_action_ids: tuple[str, ...] = ()
    conflicted_action_ids: tuple[str, ...] = ()
    dry_run: bool = True


def scan_orphan_pending_actions(
    *,
    session_store: SessionStore,
    pending_action_store: PendingActionMaintenanceStore,
    now: datetime | None = None,
) -> tuple[OrphanPendingActionReport, ...]:
    """只读扫描 PendingAction 引用关系。"""

    checked_at = _require_aware_utc(now or utc_now(), "now")
    actions = sorted(pending_action_store.list_all(), key=lambda action: action.action_id)
    return tuple(
        _classify_action(
            action=action,
            session=session_store.get(action.session_id),
            now=checked_at,
        )
        for action in actions
    )


def cleanup_orphan_pending_actions(
    *,
    session_store: SessionStore,
    pending_action_store: PendingActionMaintenanceStore,
    now: datetime | None = None,
    dry_run: bool = True,
    terminal_retention_seconds: float = 24 * 60 * 60,
) -> OrphanPendingActionMaintenanceResult:
    """按安全规则维护 orphan PendingAction。

    默认 dry-run 不写 Store。非 dry-run 时也只会：
    - 将未引用且已过期的 PENDING 标记为 EXPIRED；
    - 删除超过 retention cutoff 且未被引用的终态 Action。
    APPROVED/EXECUTING 永远只报告，不自动重试、失败或删除。
    """

    if terminal_retention_seconds < 0:
        raise ValueError("terminal_retention_seconds must be non-negative")
    checked_at = _require_aware_utc(now or utc_now(), "now")
    reports: list[OrphanPendingActionReport] = []
    expired_ids: list[str] = []
    deleted_ids: list[str] = []
    conflicted_ids: list[str] = []

    actions = sorted(pending_action_store.list_all(), key=lambda action: action.action_id)
    for action in actions:
        session = session_store.get(action.session_id)
        report = _classify_action(action=action, session=session, now=checked_at)
        reports.append(report)
        if dry_run:
            continue

        if report.classification == OrphanPendingActionClassification.EXPIRED_PENDING:
            try:
                expired = transition_pending_action(
                    action,
                    PendingActionStatus.EXPIRED,
                    now=checked_at,
                    decision_reason="orphan pending action expired by maintenance",
                )
                pending_action_store.save(expired, expected_version=action.version)
                expired_ids.append(action.action_id)
            except (PendingActionVersionConflictError, PendingActionNotFoundError):
                conflicted_ids.append(action.action_id)
            continue

        if (
            report.classification == OrphanPendingActionClassification.ORPHAN_TERMINAL
            and not report.referenced
            and _terminal_retention_elapsed(
                action,
                now=checked_at,
                retention=timedelta(seconds=terminal_retention_seconds),
            )
        ):
            try:
                pending_action_store.delete(
                    action.action_id,
                    expected_version=action.version,
                )
                deleted_ids.append(action.action_id)
            except (PendingActionVersionConflictError, PendingActionNotFoundError):
                conflicted_ids.append(action.action_id)

    return OrphanPendingActionMaintenanceResult(
        reports=tuple(reports),
        expired_action_ids=tuple(expired_ids),
        deleted_action_ids=tuple(deleted_ids),
        conflicted_action_ids=tuple(conflicted_ids),
        dry_run=dry_run,
    )


def _classify_action(
    *,
    action: PendingAction,
    session: AgentSession | None,
    now: datetime,
) -> OrphanPendingActionReport:
    referenced = _is_referenced(action=action, session=session)
    if action.status == PendingActionStatus.PENDING:
        if referenced:
            classification = OrphanPendingActionClassification.REFERENCED_PENDING
        elif _require_aware_utc(now, "now") >= action.expires_at:
            classification = OrphanPendingActionClassification.EXPIRED_PENDING
        elif session is None:
            classification = OrphanPendingActionClassification.UNREFERENCED_PENDING
        else:
            classification = OrphanPendingActionClassification.SESSION_REFERENCE_MISMATCH
    elif action.status == PendingActionStatus.APPROVED:
        classification = OrphanPendingActionClassification.ORPHAN_APPROVED
    elif action.status == PendingActionStatus.EXECUTING:
        classification = OrphanPendingActionClassification.ORPHAN_EXECUTING
    elif action.status in TERMINAL_PENDING_ACTION_STATUSES:
        classification = OrphanPendingActionClassification.ORPHAN_TERMINAL
    else:
        classification = OrphanPendingActionClassification.SESSION_REFERENCE_MISMATCH

    return OrphanPendingActionReport(
        action_id=action.action_id,
        session_id=action.session_id,
        status=action.status,
        classification=classification,
        referenced=referenced,
        created_at=action.created_at,
        updated_at=action.updated_at,
        expires_at=action.expires_at,
        resolved_at=action.resolved_at,
    )


def _is_referenced(
    *,
    action: PendingAction,
    session: AgentSession | None,
) -> bool:
    return (
        session is not None
        and action.session_id == session.session_id
        and session.status == AgentSessionStatus.WAITING_CONFIRMATION
        and session.pending_action_id == action.action_id
    )


def _terminal_retention_elapsed(
    action: PendingAction,
    *,
    now: datetime,
    retention: timedelta,
) -> bool:
    reference_time = action.resolved_at or action.updated_at
    return _require_aware_utc(now, "now") >= reference_time + retention


def _require_aware_utc(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)
