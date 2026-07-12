"""Identity SQLAlchemy 持久化模型与 Repository。

所属层：Identity / Adapters。
职责：identity Schema 映射、查询和聚合持久化。
边界：不 commit、不调用其他模块 Repository、不执行远程 I/O。
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, select
from sqlalchemy.dialects.postgresql import ARRAY, insert
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from health_platform.modules.identity.application.ports import (
    AccessGrant,
    AuthorizationGrant,
    IdentityJob,
    MfaState,
    OAuthClient,
    OneTimeGrant,
)
from health_platform.modules.identity.domain.models import (
    AccountDeletionRequest,
    IdentityError,
    IdentitySession,
    RecoveryCode,
    RefreshTokenRecord,
    Role,
    SessionStatus,
    TokenFamily,
    TokenFamilyStatus,
    UserAccount,
    UserStatus,
    utc_now,
)
from health_platform.platform.database.core import Base
from health_platform.platform.encryption.service import EncryptedValue


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


class AuthorizationGrantRow(Base):
    """一次性 Authorization Code 的数据库权威状态。"""

    __tablename__ = "authorization_grants"
    __table_args__ = (
        Index("uq_identity_authorization_code_hash", "code_hash", unique=True),
        {"schema": "identity"},
    )
    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    client_id: Mapped[str] = mapped_column(String(128), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False)
    nonce: Mapped[str] = mapped_column(String(256), nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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


class DeletionRequestRow(Base):
    """Identity 账号删除冷静期请求。"""

    __tablename__ = "deletion_requests"
    __table_args__ = (Index("ix_identity_deletion_user", "user_id"), {"schema": "identity"})
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
        self._session.add(self.to_row(user))

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
        return self.to_domain(row) if row else None

    def get(self, user_id: UUID, *, for_update: bool = False) -> UserAccount | None:
        """按 ID 读取用户；安全状态变更可请求行锁。"""
        query = self._session.query(UserRow).filter(UserRow.id == user_id)
        if for_update:
            query = query.with_for_update()
        row = query.one_or_none()
        return self.to_domain(row) if row else None

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

    def list_all(self) -> list[UserAccount]:
        return [self.to_domain(row) for row in self._session.scalars(select(UserRow)).all()]

    @staticmethod
    def to_row(user: UserAccount) -> UserRow:
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
    def to_domain(row: UserRow) -> UserAccount:
        try:
            roles = {Role(role) for role in row.roles}
        except ValueError as exc:
            raise IdentityError("IDENTITY_UNKNOWN_ROLE", "账号角色无效") from exc
        if Role.USER not in roles:
            raise IdentityError("IDENTITY_UNKNOWN_ROLE", "账号角色无效")
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
            roles=roles,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class SqlSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: IdentitySession) -> None:
        self._session.add(self.to_row(value))

    def get(self, session_id: UUID) -> IdentitySession | None:
        row = self._session.get(SessionRow, session_id)
        return self.to_domain(row) if row else None

    def save(self, value: IdentitySession) -> None:
        row = self._session.get(SessionRow, value.id)
        if row is None:
            raise LookupError("identity session not found")
        row.status = value.status.value
        row.last_login_at = value.last_login_at
        row.last_activity_at = value.last_activity_at
        row.revoked_at = value.revoked_at

    def list_for_user(self, user_id: UUID) -> list[IdentitySession]:
        rows = self._session.scalars(select(SessionRow).where(SessionRow.user_id == user_id)).all()
        return [self.to_domain(row) for row in rows]

    @staticmethod
    def to_row(value: IdentitySession) -> SessionRow:
        return SessionRow(
            id=value.id,
            user_id=value.user_id,
            client_id=value.client_id,
            device_name=value.device_name,
            client_type=value.client_type,
            status=value.status.value,
            created_at=value.created_at,
            last_login_at=value.last_login_at,
            last_activity_at=value.last_activity_at,
            revoked_at=value.revoked_at,
        )

    @staticmethod
    def to_domain(row: SessionRow) -> IdentitySession:
        return IdentitySession(
            id=row.id,
            user_id=row.user_id,
            client_id=row.client_id,
            device_name=row.device_name,
            client_type=row.client_type,
            status=SessionStatus(row.status),
            created_at=row.created_at,
            last_login_at=row.last_login_at,
            last_activity_at=row.last_activity_at,
            revoked_at=row.revoked_at,
        )


class SqlAccessGrantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: AccessGrant) -> None:
        self._session.add(self.to_row(value))

    def get_by_hash(self, token_hash: str) -> AccessGrant | None:
        row = self._session.scalar(
            select(AccessTokenRow).where(AccessTokenRow.token_hash == token_hash)
        )
        return self.to_domain(row) if row else None

    def list_for_session(self, session_id: UUID) -> list[AccessGrant]:
        rows = self._session.scalars(
            select(AccessTokenRow).where(AccessTokenRow.session_id == session_id)
        ).all()
        return [self.to_domain(row) for row in rows]

    def list_for_user(self, user_id: UUID) -> list[AccessGrant]:
        rows = self._session.scalars(
            select(AccessTokenRow).where(AccessTokenRow.user_id == user_id)
        ).all()
        return [self.to_domain(row) for row in rows]

    def save(self, value: AccessGrant) -> None:
        row = self._session.scalar(
            select(AccessTokenRow).where(AccessTokenRow.token_hash == value.token_hash)
        )
        if row is None:
            raise LookupError("access grant not found")
        row.revoked_at = value.revoked_at

    @staticmethod
    def to_row(value: AccessGrant) -> AccessTokenRow:
        return AccessTokenRow(
            token_hash=value.token_hash,
            user_id=value.user_id,
            session_id=value.session_id,
            client_id=value.client_id,
            audience=value.audience,
            scopes=list(value.scopes),
            permission_version=value.permission_version,
            expires_at=value.expires_at,
            revoked_at=value.revoked_at,
        )

    @staticmethod
    def to_domain(row: AccessTokenRow) -> AccessGrant:
        return AccessGrant(
            token_hash=row.token_hash,
            user_id=row.user_id,
            session_id=row.session_id,
            client_id=row.client_id,
            audience=row.audience,
            scopes=tuple(row.scopes),
            permission_version=row.permission_version,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
        )


class SqlRefreshTokenRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, family_id: UUID, value: RefreshTokenRecord) -> None:
        self._session.add(self.to_row(family_id, value))

    def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        row = self._session.scalar(
            select(RefreshTokenRow).where(RefreshTokenRow.token_hash == token_hash)
        )
        return self.to_domain(row) if row else None

    def list_for_family(self, family_id: UUID) -> list[RefreshTokenRecord]:
        rows = self._session.scalars(
            select(RefreshTokenRow)
            .where(RefreshTokenRow.family_id == family_id)
            .order_by(RefreshTokenRow.issued_at)
        ).all()
        return [self.to_domain(row) for row in rows]

    @staticmethod
    def to_row(family_id: UUID, value: RefreshTokenRecord) -> RefreshTokenRow:
        return RefreshTokenRow(
            id=value.id,
            family_id=family_id,
            token_hash=value.token_hash,
            issued_at=value.issued_at,
            expires_at=value.expires_at,
            consumed_at=value.consumed_at,
            replaced_by_id=value.replaced_by_id,
        )

    @staticmethod
    def to_domain(row: RefreshTokenRow) -> RefreshTokenRecord:
        return RefreshTokenRecord(
            id=row.id,
            token_hash=row.token_hash,
            issued_at=row.issued_at,
            expires_at=row.expires_at,
            consumed_at=row.consumed_at,
            replaced_by_id=row.replaced_by_id,
        )


class SqlTokenFamilyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: TokenFamily) -> None:
        self._session.add(self.to_row(value))

    def get(self, family_id: UUID, *, for_update: bool = False) -> TokenFamily | None:
        statement = select(TokenFamilyRow).where(TokenFamilyRow.id == family_id)
        if for_update:
            statement = statement.with_for_update()
        row = self._session.scalar(statement)
        return self.to_domain(row) if row else None

    def find_by_refresh_hash(self, presented_hash: str) -> TokenFamily | None:
        row = self._session.scalar(
            select(TokenFamilyRow)
            .join(RefreshTokenRow, RefreshTokenRow.family_id == TokenFamilyRow.id)
            .where(RefreshTokenRow.token_hash == presented_hash)
            .with_for_update(of=TokenFamilyRow)
        )
        return self.to_domain(row) if row else None

    def save(self, value: TokenFamily) -> None:
        self._session.flush()
        row = self._session.get(TokenFamilyRow, value.id)
        if row is None:
            raise LookupError("token family not found")
        row.status = value.status.value
        row.revoked_at = value.revoked_at
        existing = {
            item.id: item
            for item in self._session.scalars(
                select(RefreshTokenRow).where(RefreshTokenRow.family_id == value.id)
            ).all()
        }
        for token in value.tokens:
            token_row = existing.get(token.id)
            if token_row is None:
                self._session.add(SqlRefreshTokenRepository.to_row(value.id, token))
            else:
                token_row.consumed_at = token.consumed_at
                token_row.replaced_by_id = token.replaced_by_id

    def list_for_session(self, session_id: UUID) -> list[TokenFamily]:
        rows = self._session.scalars(
            select(TokenFamilyRow).where(TokenFamilyRow.session_id == session_id)
        ).all()
        return [self.to_domain(row) for row in rows]

    @staticmethod
    def to_row(value: TokenFamily) -> TokenFamilyRow:
        return TokenFamilyRow(
            id=value.id,
            user_id=value.user_id,
            session_id=value.session_id,
            status=value.status.value,
            revoked_at=value.revoked_at,
        )

    def to_domain(self, row: TokenFamilyRow) -> TokenFamily:
        return TokenFamily(
            id=row.id,
            user_id=row.user_id,
            session_id=row.session_id,
            status=TokenFamilyStatus(row.status),
            revoked_at=row.revoked_at,
            tokens=SqlRefreshTokenRepository(self._session).list_for_family(row.id),
        )


class SqlOneTimeTokenRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: OneTimeGrant) -> None:
        self._session.add(self.to_row(value))

    def invalidate_for_user_kind(self, user_id: UUID, kind: str, now: datetime) -> None:
        rows = self._session.scalars(
            select(OneTimeTokenRow)
            .where(
                OneTimeTokenRow.user_id == user_id,
                OneTimeTokenRow.kind == kind,
                OneTimeTokenRow.consumed_at.is_(None),
                OneTimeTokenRow.invalidated_at.is_(None),
            )
            .with_for_update()
        ).all()
        for row in rows:
            row.invalidated_at = now

    def consume(self, token_hash: str, kind: str, now: datetime) -> OneTimeGrant | None:
        row = self._session.scalar(
            select(OneTimeTokenRow)
            .where(OneTimeTokenRow.token_hash == token_hash, OneTimeTokenRow.kind == kind)
            .with_for_update()
        )
        if (
            row is None
            or row.consumed_at is not None
            or row.invalidated_at is not None
            or row.expires_at <= now
        ):
            return None
        row.consumed_at = now
        return self.to_domain(row)

    @staticmethod
    def to_row(value: OneTimeGrant) -> OneTimeTokenRow:
        return OneTimeTokenRow(
            user_id=value.user_id,
            kind=value.kind,
            token_hash=value.token_hash,
            payload=dict(value.payload),
            expires_at=value.expires_at,
            consumed_at=value.consumed_at,
            invalidated_at=value.invalidated_at,
        )

    @staticmethod
    def to_domain(row: OneTimeTokenRow) -> OneTimeGrant:
        return OneTimeGrant(
            user_id=row.user_id,
            kind=row.kind,
            token_hash=row.token_hash,
            payload={str(key): str(value) for key, value in row.payload.items()},
            expires_at=row.expires_at,
            consumed_at=row.consumed_at,
            invalidated_at=row.invalidated_at,
        )


class SqlMfaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: UUID) -> MfaState | None:
        row = self._session.scalar(
            select(MfaEnrollmentRow).where(MfaEnrollmentRow.user_id == user_id)
        )
        return self.to_domain(row) if row else None

    def add(self, user_id: UUID, value: MfaState) -> None:
        enrollment = self.to_row(user_id, value)
        self._session.add(enrollment)
        self._session.flush()
        for code in value.recovery_codes:
            self._session.add(self.recovery_to_row(enrollment.id, code))

    def save(self, user_id: UUID, value: MfaState) -> None:
        row = self._session.scalar(
            select(MfaEnrollmentRow).where(MfaEnrollmentRow.user_id == user_id).with_for_update()
        )
        if row is None:
            raise LookupError("mfa enrollment not found")
        row.ciphertext = value.encrypted_secret.ciphertext
        row.nonce = value.encrypted_secret.nonce
        row.key_version = value.encrypted_secret.key_version
        row.algorithm = value.encrypted_secret.algorithm
        row.enabled = value.enabled
        existing = {
            item.code_hash: item
            for item in self._session.scalars(
                select(RecoveryCodeRow).where(RecoveryCodeRow.enrollment_id == row.id)
            ).all()
        }
        for code in value.recovery_codes:
            code_row = existing.get(code.code_hash)
            if code_row is None:
                self._session.add(self.recovery_to_row(row.id, code))
            else:
                code_row.used_at = code.used_at

    @staticmethod
    def to_row(user_id: UUID, value: MfaState) -> MfaEnrollmentRow:
        return MfaEnrollmentRow(
            user_id=user_id,
            ciphertext=value.encrypted_secret.ciphertext,
            nonce=value.encrypted_secret.nonce,
            key_version=value.encrypted_secret.key_version,
            algorithm=value.encrypted_secret.algorithm,
            enabled=value.enabled,
            created_at=utc_now(),
            confirmed_at=utc_now() if value.enabled else None,
        )

    @staticmethod
    def recovery_to_row(enrollment_id: UUID, value: RecoveryCode) -> RecoveryCodeRow:
        return RecoveryCodeRow(
            enrollment_id=enrollment_id, code_hash=value.code_hash, used_at=value.used_at
        )

    def to_domain(self, row: MfaEnrollmentRow) -> MfaState:
        codes = self._session.scalars(
            select(RecoveryCodeRow).where(RecoveryCodeRow.enrollment_id == row.id)
        ).all()
        return MfaState(
            encrypted_secret=EncryptedValue(
                ciphertext=row.ciphertext,
                nonce=row.nonce,
                key_version=row.key_version,
                algorithm=row.algorithm,
            ),
            enabled=row.enabled,
            recovery_codes=[RecoveryCode(code.code_hash, code.used_at) for code in codes],
        )


class SqlOAuthClientRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, value: OAuthClient) -> None:
        self._session.execute(
            insert(OAuthClientRow)
            .values(
                client_id=value.client_id,
                redirect_uris=list(value.redirect_uris),
                allowed_scopes=list(value.allowed_scopes),
                allowed_audiences=[value.audience],
                public_client=value.public,
                active=True,
            )
            .on_conflict_do_nothing(index_elements=[OAuthClientRow.client_id])
        )
        existing = self._session.get(OAuthClientRow, value.client_id)
        if existing is None or self.to_domain(existing) != value:
            raise IdentityError("IDENTITY_OAUTH_CLIENT_CONFLICT", "OAuth Client 配置冲突")

    def get(self, client_id: str) -> OAuthClient | None:
        row = self._session.get(OAuthClientRow, client_id)
        return self.to_domain(row) if row and row.active else None

    @staticmethod
    def to_row(value: OAuthClient) -> OAuthClientRow:
        return OAuthClientRow(
            client_id=value.client_id,
            redirect_uris=list(value.redirect_uris),
            allowed_scopes=list(value.allowed_scopes),
            allowed_audiences=[value.audience],
            public_client=value.public,
            active=True,
        )

    @staticmethod
    def to_domain(row: OAuthClientRow) -> OAuthClient:
        if len(row.allowed_audiences) != 1:
            raise IdentityError("IDENTITY_OAUTH_CLIENT_INVALID", "OAuth Client 配置无效")
        return OAuthClient(
            client_id=row.client_id,
            redirect_uris=tuple(row.redirect_uris),
            allowed_scopes=tuple(row.allowed_scopes),
            audience=row.allowed_audiences[0],
            public=row.public_client,
        )


class SqlAuthorizationGrantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, code_hash: str, value: AuthorizationGrant) -> None:
        self._session.add(self.to_row(code_hash, value))

    def consume(self, code_hash: str) -> AuthorizationGrant | None:
        row = self._session.scalar(
            select(AuthorizationGrantRow)
            .where(AuthorizationGrantRow.code_hash == code_hash)
            .with_for_update()
        )
        if row is None or row.consumed_at is not None:
            return None
        grant = self.to_domain(row)
        row.consumed_at = utc_now()
        return grant

    @staticmethod
    def to_row(code_hash: str, value: AuthorizationGrant) -> AuthorizationGrantRow:
        return AuthorizationGrantRow(
            code_hash=code_hash,
            user_id=value.user_id,
            client_id=value.client_id,
            redirect_uri=value.redirect_uri,
            scopes=list(value.scope),
            nonce=value.nonce,
            code_challenge=value.code_challenge,
            expires_at=value.expires_at,
            consumed_at=value.consumed_at,
        )

    @staticmethod
    def to_domain(row: AuthorizationGrantRow) -> AuthorizationGrant:
        return AuthorizationGrant(
            user_id=row.user_id,
            client_id=row.client_id,
            redirect_uri=row.redirect_uri,
            scope=tuple(row.scopes),
            nonce=row.nonce,
            code_challenge=row.code_challenge,
            expires_at=row.expires_at,
            consumed_at=row.consumed_at,
        )


class SqlJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, job_id: UUID, user_id: UUID, kind: str, status: str, payload: dict[str, str]
    ) -> None:
        self._session.add(self.to_row(IdentityJob(job_id, user_id, kind, status, payload)))

    def get(self, job_id: UUID) -> IdentityJob | None:
        row = self._session.get(IdentityJobRow, job_id)
        return self.to_domain(row) if row else None

    @staticmethod
    def to_row(value: IdentityJob) -> IdentityJobRow:
        return IdentityJobRow(
            id=value.id,
            user_id=value.user_id,
            kind=value.kind,
            status=value.status,
            payload=dict(value.payload),
            created_at=value.created_at or utc_now(),
            ready_at=value.ready_at,
            completed_at=value.completed_at,
        )

    @staticmethod
    def to_domain(row: IdentityJobRow) -> IdentityJob:
        return IdentityJob(
            id=row.id,
            user_id=row.user_id,
            kind=row.kind,
            status=row.status,
            payload={str(key): str(value) for key, value in row.payload.items()},
            created_at=row.created_at,
            ready_at=row.ready_at,
            completed_at=row.completed_at,
        )


class SqlDeletionRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, value: AccountDeletionRequest) -> None:
        self._session.add(self.to_row(value))

    def get(self, request_id: UUID) -> AccountDeletionRequest | None:
        row = self._session.get(DeletionRequestRow, request_id)
        return self.to_domain(row) if row else None

    @staticmethod
    def to_row(value: AccountDeletionRequest) -> DeletionRequestRow:
        return DeletionRequestRow(
            id=value.id,
            user_id=value.user_id,
            requested_at=value.requested_at,
            cancelled_at=value.cancelled_at,
            completed_at=value.completed_at,
        )

    @staticmethod
    def to_domain(row: DeletionRequestRow) -> AccountDeletionRequest:
        return AccountDeletionRequest(
            id=row.id,
            user_id=row.user_id,
            requested_at=row.requested_at,
            cancelled_at=row.cancelled_at,
            completed_at=row.completed_at,
        )
