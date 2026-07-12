"""Identity SQLAlchemy 持久化模型与 Repository。

所属层：Identity / Adapters。
职责：identity Schema 映射、查询和聚合持久化。
边界：不 commit、不调用其他模块 Repository、不执行远程 I/O。
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from health_platform.modules.identity.domain.models import UserAccount, UserStatus
from health_platform.platform.database.core import Base


class UserRow(Base):
    """用户账号持久化模型；与 Domain/API DTO 保持显式映射。"""

    __tablename__ = "users"
    __table_args__ = (
        Index("uq_identity_users_email", "email_normalized", unique=True),
        Index("uq_identity_users_username", "username_normalized", unique=True),
        {"schema": "identity"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    username_normalized: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    permission_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SessionRow(Base):
    """设备会话和客户端摘要。"""

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_identity_sessions_user", "user_id"), {"schema": "identity"})
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    client_id: Mapped[str] = mapped_column(String(128), nullable=False)
    device_name: Mapped[str] = mapped_column(String(200), nullable=False)
    client_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    last_ip_prefix: Mapped[str | None] = mapped_column(String(64))
    last_region: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccessTokenRow(Base):
    """可即时撤销的不透明 Access Token 哈希。"""

    __tablename__ = "access_tokens"
    __table_args__ = (
        Index("uq_identity_access_token_hash", "token_hash", unique=True),
        Index("ix_identity_access_tokens_user", "user_id"),
        {"schema": "identity"},
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    client_id: Mapped[str] = mapped_column(String(128), nullable=False)
    audience: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False)
    permission_version: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TokenFamilyRow(Base):
    """设备级 Refresh Token Family 权威状态。"""

    __tablename__ = "token_families"
    __table_args__ = ({"schema": "identity"},)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshTokenRow(Base):
    """一次性 Refresh Token 哈希和轮换链。"""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("uq_identity_refresh_hash", "token_hash", unique=True),
        {"schema": "identity"},
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    family_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("identity.token_families.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))


class OneTimeTokenRow(Base):
    """邮箱验证、密码恢复和一次性授权码的哈希载体。"""

    __tablename__ = "one_time_tokens"
    __table_args__ = (
        Index("uq_identity_one_time_hash", "token_hash", unique=True),
        Index("ix_identity_one_time_user_kind", "user_id", "kind"),
        {"schema": "identity"},
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MfaEnrollmentRow(Base):
    """TOTP 加密信封和启用状态；不保存明文 Secret。"""

    __tablename__ = "mfa_enrollments"
    __table_args__ = ({"schema": "identity"},)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), unique=True, nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    key_version: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecoveryCodeRow(Base):
    """一次性 MFA 恢复码哈希。"""

    __tablename__ = "recovery_codes"
    __table_args__ = ({"schema": "identity"},)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    enrollment_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthClientRow(Base):
    """受配置管理的第一方 OAuth Client。"""

    __tablename__ = "oauth_clients"
    __table_args__ = ({"schema": "identity"},)
    client_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    client_secret_hash: Mapped[str | None] = mapped_column(Text)
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    allowed_scopes: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False)
    allowed_audiences: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False)
    public_client: Mapped[bool] = mapped_column(Boolean, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class IdentityJobRow(Base):
    """导出与账号删除任务框架；其他模块完成度不得在此伪造。"""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_identity_jobs_user_kind", "user_id", "kind"),
        {"schema": "identity"},
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SecurityEventRow(Base):
    """账号安全事件摘要；不保存密码、Token 或完整敏感标识。"""

    __tablename__ = "security_events"
    __table_args__ = (Index("ix_identity_security_events_user", "user_id"), {"schema": "identity"})
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )


class IdempotencyRow(Base):
    """用户/Client/Endpoint 绑定的幂等响应记录。"""

    __tablename__ = "idempotency_records"
    __table_args__ = (
        Index(
            "uq_identity_idempotency_scope", "user_id", "client_id", "endpoint", "key", unique=True
        ),
        {"schema": "identity"},
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    client_id: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SqlUserRepository:
    """UserAccount SQL Repository；事务提交由外层 UoW 统一执行。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: UserAccount) -> None:
        """新增用户映射；唯一冲突由数据库约束和应用错误转换处理。"""
        self._session.add(self._to_row(user))

    def get_by_identifier(self, normalized_identifier: str) -> UserAccount | None:
        """按已规范化邮箱或用户名查找账号，不改变登录错误语义。"""
        row = (
            self._session.query(UserRow)
            .filter(
                (UserRow.email_normalized == normalized_identifier)
                | (UserRow.username_normalized == normalized_identifier)
            )
            .one_or_none()
        )
        return self._to_domain(row) if row else None

    def get(self, user_id: UUID, *, for_update: bool = False) -> UserAccount | None:
        """按 ID 读取用户；安全状态变更可请求行锁。"""
        query = self._session.query(UserRow).filter(UserRow.id == user_id)
        if for_update:
            query = query.with_for_update()
        row = query.one_or_none()
        return self._to_domain(row) if row else None

    def save(self, user: UserAccount) -> None:
        """更新聚合快照但不 commit，确保审计与 Outbox 可同事务加入。"""
        row = self._session.get(UserRow, user.id)
        if row is None:
            raise LookupError("user not found")
        row.email_normalized = user.email
        row.username_normalized = user.username
        row.display_name = user.display_name
        row.password_hash = user.password_hash
        row.status = user.status.value
        row.email_verified_at = user.email_verified_at
        row.permission_version = user.permission_version
        row.failed_login_count = user.failed_login_count
        row.locked_until = user.locked_until
        row.roles = [role.value for role in user.roles]
        row.updated_at = user.updated_at

    @staticmethod
    def _to_row(user: UserAccount) -> UserRow:
        return UserRow(
            id=user.id,
            email_normalized=user.email,
            username_normalized=user.username,
            display_name=user.display_name,
            password_hash=user.password_hash,
            status=user.status.value,
            email_verified_at=user.email_verified_at,
            permission_version=user.permission_version,
            failed_login_count=user.failed_login_count,
            locked_until=user.locked_until,
            roles=[role.value for role in user.roles],
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    @staticmethod
    def _to_domain(row: UserRow) -> UserAccount:
        from health_platform.modules.identity.domain.models import Role

        return UserAccount(
            id=row.id,
            email=row.email_normalized,
            username=row.username_normalized,
            display_name=row.display_name,
            password_hash=row.password_hash,
            status=UserStatus(row.status),
            email_verified_at=row.email_verified_at,
            permission_version=row.permission_version,
            failed_login_count=row.failed_login_count,
            locked_until=row.locked_until,
            roles={Role(role) for role in row.roles},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
