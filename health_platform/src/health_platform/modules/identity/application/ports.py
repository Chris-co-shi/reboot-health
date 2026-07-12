"""Identity 应用层 Port Protocol。

所属层：Identity / Application。
职责：声明 IdentityService 所需的全部依赖抽象（UoW、Repository、Audit、Outbox），
     Application 不允许 import SQLAlchemy、SQLAlchemy Session 或具体实现。
边界：仅依赖领域 dataclass 与 typing。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from health_platform.modules.audit.domain.models import AuditEvent, OutboxEvent
from health_platform.modules.identity.domain.models import (
    AccountDeletionRequest,
    IdentitySession,
    RecoveryCode,
    RefreshTokenRecord,
    TokenFamily,
    UserAccount,
)
from health_platform.platform.encryption.service import EncryptedValue


@dataclass(frozen=True)
class OAuthClient:
    """预注册第一方 Client；redirect、scope 和 audience 均为确定性白名单。"""

    client_id: str
    redirect_uris: tuple[str, ...]
    allowed_scopes: tuple[str, ...]
    audience: str
    public: bool = True


@dataclass
class AccessGrant:
    """不透明 Access Token 的权威最小状态。"""

    token_hash: str
    user_id: UUID
    session_id: UUID
    client_id: str
    audience: str
    scopes: tuple[str, ...]
    permission_version: int
    expires_at: datetime
    revoked_at: datetime | None = None


@dataclass
class OneTimeGrant:
    """一次性短期验证/恢复/授权凭证。"""

    user_id: UUID
    kind: str
    token_hash: str
    expires_at: datetime
    payload: dict[str, str] = field(default_factory=dict)
    consumed_at: datetime | None = None
    invalidated_at: datetime | None = None


@dataclass
class MfaState:
    """用户 MFA 加密状态与一次性恢复码。"""

    encrypted_secret: EncryptedValue
    enabled: bool = False
    recovery_codes: list[RecoveryCode] = field(default_factory=list)


@dataclass
class AuthorizationGrant:
    """短期一次性 Authorization Code 哈希记录。"""

    user_id: UUID
    client_id: str
    redirect_uri: str
    scope: tuple[str, ...]
    nonce: str
    code_challenge: str
    expires_at: datetime
    consumed_at: datetime | None = None


# -----------------------------
# Audit / Outbox 端口
# -----------------------------


@runtime_checkable
class AuditPort(Protocol):
    """追加审计端口；实现负责 previous_hash 链安全。"""

    def current_hash(self) -> str:
        """返回当前事件链头哈希；缺链头返回 GENESIS。"""

    def append(self, event: AuditEvent) -> str:
        """同事务追加审计事件并返回写入的 event_hash。"""

    def entries(self) -> list[AuditEvent]:
        """用于测试与回滚断言；生产实现可返回空或抛出。"""


@runtime_checkable
class OutboxPort(Protocol):
    """Outbox 端口；实现负责同事务持久化可靠副作用。"""

    def enqueue(self, event: OutboxEvent) -> None:
        """同事务入队待发布副作用。"""

    def entries(self) -> list[OutboxEvent]:
        """用于测试与回滚断言。"""


# -----------------------------
# Repository 端口
# -----------------------------


@runtime_checkable
class UserRepository(Protocol):
    def add(self, user: UserAccount) -> None: ...
    def get(self, user_id: UUID, *, for_update: bool = False) -> UserAccount | None: ...
    def get_by_identifier(self, normalized_identifier: str) -> UserAccount | None: ...
    def save(self, user: UserAccount) -> None: ...
    def list_all(self) -> list[UserAccount]: ...


@runtime_checkable
class SessionRepository(Protocol):
    def add(self, session: IdentitySession) -> None: ...
    def get(self, session_id: UUID) -> IdentitySession | None: ...
    def save(self, session: IdentitySession) -> None: ...
    def list_for_user(self, user_id: UUID) -> list[IdentitySession]: ...


@runtime_checkable
class TokenFamilyRepository(Protocol):
    def add(self, family: TokenFamily) -> None: ...
    def get(self, family_id: UUID, *, for_update: bool = False) -> TokenFamily | None: ...
    def find_by_refresh_hash(self, presented_hash: str) -> TokenFamily | None: ...
    def save(self, family: TokenFamily) -> None: ...
    def list_for_session(self, session_id: UUID) -> list[TokenFamily]: ...


@runtime_checkable
class RefreshTokenRepository(Protocol):
    def add(self, family_id: UUID, record: RefreshTokenRecord) -> None: ...
    def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None: ...
    def list_for_family(self, family_id: UUID) -> list[RefreshTokenRecord]: ...


@runtime_checkable
class AccessGrantRepository(Protocol):
    """Access Token 状态仓库；状态由 IdentityService 维护在 AccessGrant dataclass 中。"""

    def add(self, grant: AccessGrant) -> None: ...
    def get_by_hash(self, token_hash: str) -> AccessGrant | None: ...
    def list_for_session(self, session_id: UUID) -> list[AccessGrant]: ...
    def list_for_user(self, user_id: UUID) -> list[AccessGrant]: ...
    def save(self, grant: AccessGrant) -> None: ...


@runtime_checkable
class OneTimeTokenRepository(Protocol):
    def add(self, grant: OneTimeGrant) -> None: ...
    def invalidate_for_user_kind(self, user_id: UUID, kind: str, now: datetime) -> None: ...
    def consume(self, token_hash: str, kind: str, now: datetime) -> OneTimeGrant | None: ...


@runtime_checkable
class MfaRepository(Protocol):
    def get(self, user_id: UUID) -> MfaState | None: ...
    def add(self, user_id: UUID, state: MfaState) -> None: ...
    def save(self, user_id: UUID, state: MfaState) -> None: ...


@runtime_checkable
class OAuthClientRepository(Protocol):
    def upsert(self, client: OAuthClient) -> None:
        """多 Pod 幂等；重复调用不抛错。"""
        ...

    def get(self, client_id: str) -> OAuthClient | None: ...


@runtime_checkable
class AuthorizationGrantRepository(Protocol):
    def add(self, code_hash: str, grant: AuthorizationGrant) -> None: ...
    def consume(self, code_hash: str) -> AuthorizationGrant | None: ...


@runtime_checkable
class JobRepository(Protocol):
    def add(
        self, job_id: UUID, user_id: UUID, kind: str, status: str, payload: dict[str, str]
    ) -> None: ...


@runtime_checkable
class DeletionRequestRepository(Protocol):
    def add(self, request: AccountDeletionRequest) -> None: ...
    def get(self, request_id: UUID) -> AccountDeletionRequest | None: ...


# -----------------------------
# UnitOfWork 端口
# -----------------------------


@runtime_checkable
class IdentityUnitOfWork(Protocol):
    users: UserRepository
    sessions: SessionRepository
    access_grants: AccessGrantRepository
    token_families: TokenFamilyRepository
    refresh_tokens: RefreshTokenRepository
    one_time_tokens: OneTimeTokenRepository
    mfa: MfaRepository
    oauth_clients: OAuthClientRepository
    authorization_grants: AuthorizationGrantRepository
    jobs: JobRepository
    deletion_requests: DeletionRequestRepository
    audit: AuditPort
    outbox: OutboxPort

    def __enter__(self) -> IdentityUnitOfWork: ...
    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def set_security_context(self, user_id: UUID | None, actor_kind: str) -> None: ...
    def run_after_commit(self, hook: Callable[[], object]) -> None: ...


UoWFactory = Callable[[], IdentityUnitOfWork]
