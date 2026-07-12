"""InMemory IdentityUnitOfWork 与 Repository 适配器。

所属层：Identity / Application（Adapter 实现）。
职责：测试用纯内存实现，保持与未来 SQL 实现相同的语义（事务边界、commit hooks、
     previous_hash 链、并发通过 GIL 串行保证）。
边界：仅供单元测试与本地开发使用；生产 Composition Root 改用 SqlAlchemy 实现，
     本模块不 import 任何 SQLAlchemy 类型。
"""

from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Any
from uuid import UUID

from health_platform.modules.audit.domain.models import AuditEvent, OutboxEvent
from health_platform.modules.identity.application.ports import (
    AccessGrant,
    AccessGrantRepository,
    AuditPort,
    AuthorizationGrant,
    AuthorizationGrantRepository,
    DeletionRequestRepository,
    IdentityUnitOfWork,
    JobRepository,
    MfaRepository,
    MfaState,
    OAuthClient,
    OAuthClientRepository,
    OneTimeGrant,
    OneTimeTokenRepository,
    OutboxPort,
    RefreshTokenRepository,
    SessionRepository,
    TokenFamilyRepository,
    UserRepository,
)
from health_platform.modules.identity.domain.models import (
    AccountDeletionRequest,
    IdentitySession,
    RefreshTokenRecord,
    TokenFamily,
    UserAccount,
)

# -----------------------------
# Access / OneTime / Mfa / Authorization 的"领域字典"形状
# -----------------------------


# InMemory 实现采用 dataclass 形状与既有领域类一致：AccessGrant、OneTimeGrant、
# MfaState、AuthorizationGrant 已在 application/service.py 内定义。此处仅保存对
# 象引用即可；通过 token_hash / user_id 索引以便查找。
# 为避免 Application 与 Adapter 双向耦合，InMemory 适配器只使用对象本身的字段。
# AccessGrant、OneTimeGrant、MfaState、AuthorizationGrant 由 service.py 定义。

GENESIS_HASH = "GENESIS"


# -----------------------------
# Repository 实现（InMemory）
# -----------------------------


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, UserAccount] = {}

    def add(self, user: UserAccount) -> None:
        self._by_id[user.id] = user

    def get(self, user_id: UUID, *, for_update: bool = False) -> UserAccount | None:
        return self._by_id.get(user_id)

    def get_by_identifier(self, normalized_identifier: str) -> UserAccount | None:
        for user in self._by_id.values():
            if user.email == normalized_identifier or user.username == normalized_identifier:
                return user
        return None

    def save(self, user: UserAccount) -> None:
        if user.id not in self._by_id:
            raise LookupError("user not found")
        self._by_id[user.id] = user

    def list_all(self) -> list[UserAccount]:
        return list(self._by_id.values())


class InMemorySessionRepository(SessionRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, IdentitySession] = {}

    def add(self, session: IdentitySession) -> None:
        self._by_id[session.id] = session

    def get(self, session_id: UUID) -> IdentitySession | None:
        return self._by_id.get(session_id)

    def save(self, session: IdentitySession) -> None:
        if session.id not in self._by_id:
            raise LookupError("session not found")
        self._by_id[session.id] = session

    def list_for_user(self, user_id: UUID) -> list[IdentitySession]:
        return [s for s in self._by_id.values() if s.user_id == user_id]


class InMemoryTokenFamilyRepository(TokenFamilyRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, TokenFamily] = {}

    def add(self, family: TokenFamily) -> None:
        self._by_id[family.id] = family

    def get(self, family_id: UUID, *, for_update: bool = False) -> TokenFamily | None:
        return self._by_id.get(family_id)

    def find_by_refresh_hash(self, presented_hash: str) -> TokenFamily | None:
        for family in self._by_id.values():
            for token in family.tokens:
                if token.token_hash == presented_hash:
                    return family
        return None

    def save(self, family: TokenFamily) -> None:
        if family.id not in self._by_id:
            raise LookupError("token family not found")
        self._by_id[family.id] = family

    def list_for_session(self, session_id: UUID) -> list[TokenFamily]:
        return [f for f in self._by_id.values() if f.session_id == session_id]


class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self) -> None:
        self._by_hash: dict[str, RefreshTokenRecord] = {}

    def add(self, family_id: UUID, record: RefreshTokenRecord) -> None:
        self._by_hash[record.token_hash] = record

    def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        return self._by_hash.get(token_hash)

    def list_for_family(self, family_id: UUID) -> list[RefreshTokenRecord]:
        # 因 RefreshTokenRecord 不持有 family_id，需要由 Service 通过 family.tokens 列表访问。
        return list(self._by_hash.values())


class InMemoryAccessGrantRepository(AccessGrantRepository):
    def __init__(self) -> None:
        self._by_hash: dict[str, AccessGrant] = {}

    def add(self, grant: AccessGrant) -> None:
        self._by_hash[grant.token_hash] = grant

    def get_by_hash(self, token_hash: str) -> AccessGrant | None:
        return self._by_hash.get(token_hash)

    def list_for_session(self, session_id: UUID) -> list[AccessGrant]:
        return [g for g in self._by_hash.values() if g.session_id == session_id]

    def list_for_user(self, user_id: UUID) -> list[AccessGrant]:
        return [g for g in self._by_hash.values() if g.user_id == user_id]

    def save(self, grant: AccessGrant) -> None:
        if grant.token_hash not in self._by_hash:
            raise LookupError("access grant not found")
        self._by_hash[grant.token_hash] = grant


class InMemoryOneTimeTokenRepository(OneTimeTokenRepository):
    def __init__(self) -> None:
        self._by_hash: dict[str, OneTimeGrant] = {}

    def add(self, grant: OneTimeGrant) -> None:
        self._by_hash[grant.token_hash] = grant

    def invalidate_for_user_kind(self, user_id: UUID, kind: str, now: datetime) -> None:
        for grant in self._by_hash.values():
            if grant.user_id == user_id and grant.kind == kind and grant.consumed_at is None:
                grant.invalidated_at = now

    def consume(self, token_hash: str, kind: str, now: datetime) -> OneTimeGrant | None:
        grant = self._by_hash.get(token_hash)
        if grant is None:
            return None
        if (
            grant.kind != kind
            or grant.consumed_at is not None
            or grant.invalidated_at is not None
            or grant.expires_at <= now
        ):
            return None
        grant.consumed_at = now
        return grant


class InMemoryMfaRepository(MfaRepository):
    def __init__(self) -> None:
        self._by_user: dict[UUID, MfaState] = {}

    def get(self, user_id: UUID) -> MfaState | None:
        return self._by_user.get(user_id)

    def add(self, user_id: UUID, state: MfaState) -> None:
        self._by_user[user_id] = state

    def save(self, user_id: UUID, state: MfaState) -> None:
        self._by_user[user_id] = state


class InMemoryOAuthClientRepository(OAuthClientRepository):
    def __init__(self) -> None:
        self._by_id: dict[str, OAuthClient] = {}

    def upsert(self, client: OAuthClient) -> None:
        """多 Pod 幂等：仅在缺失时写入。"""
        self._by_id.setdefault(client.client_id, client)

    def get(self, client_id: str) -> OAuthClient | None:
        return self._by_id.get(client_id)


class InMemoryAuthorizationGrantRepository(AuthorizationGrantRepository):
    def __init__(self) -> None:
        self._by_hash: dict[str, AuthorizationGrant] = {}

    def add(self, code_hash: str, grant: AuthorizationGrant) -> None:
        self._by_hash[code_hash] = grant

    def consume(self, code_hash: str) -> AuthorizationGrant | None:
        grant = self._by_hash.get(code_hash)
        if grant is None or grant.consumed_at is not None:
            return None
        return grant


class InMemoryJobRepository(JobRepository):
    def __init__(self) -> None:
        self._jobs: list[dict[str, Any]] = []

    def add(
        self, job_id: UUID, user_id: UUID, kind: str, status: str, payload: dict[str, str]
    ) -> None:
        self._jobs.append(
            {
                "job_id": job_id,
                "user_id": user_id,
                "kind": kind,
                "status": status,
                "payload": payload,
            }
        )


class InMemoryDeletionRequestRepository(DeletionRequestRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, AccountDeletionRequest] = {}

    def add(self, request: AccountDeletionRequest) -> None:
        self._by_id[request.id] = request

    def get(self, request_id: UUID) -> AccountDeletionRequest | None:
        return self._by_id.get(request_id)


# -----------------------------
# Audit / Outbox
# -----------------------------


class InMemoryAuditRepository(AuditPort):
    """保持 previous_hash 链安全。SQL 实现改用 chain_heads 行锁。"""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._head: str = GENESIS_HASH

    def current_hash(self) -> str:
        return self._head

    def append(self, event: AuditEvent) -> str:
        # 强制 previous_hash 等于当前链头，保证 A→B→C 顺序且不分叉。
        previous = self._head
        if event.previous_hash != previous:
            # 重写为链头，避免业务代码传入 stale previous_hash。
            object.__setattr__(event, "previous_hash", previous)
        self._events.append(event)
        self._head = event.event_hash
        return event.event_hash

    def entries(self) -> list[AuditEvent]:
        return list(self._events)


class InMemoryOutboxRepository(OutboxPort):
    def __init__(self) -> None:
        self._events: list[OutboxEvent] = []

    def enqueue(self, event: OutboxEvent) -> None:
        self._events.append(event)

    def entries(self) -> list[OutboxEvent]:
        return list(self._events)


# -----------------------------
# UnitOfWork
# -----------------------------


class InMemoryUnitOfWork(IdentityUnitOfWork):
    """测试用内存 UoW；保留事务语义（commit hooks）与隔离性（GIL 单线程）。

    不在事务内调用远程 I/O；Service 通过 run_after_commit 注册缓存写入与
    Outbox 副作用，确保一致性。
    """

    def __init__(self) -> None:
        self.users: UserRepository = InMemoryUserRepository()
        self.sessions: SessionRepository = InMemorySessionRepository()
        self.token_families: TokenFamilyRepository = InMemoryTokenFamilyRepository()
        self.refresh_tokens: RefreshTokenRepository = InMemoryRefreshTokenRepository()
        self.access_grants: AccessGrantRepository = InMemoryAccessGrantRepository()
        self.one_time_tokens: OneTimeTokenRepository = InMemoryOneTimeTokenRepository()
        self.mfa: MfaRepository = InMemoryMfaRepository()
        self.oauth_clients: OAuthClientRepository = InMemoryOAuthClientRepository()
        self.authorization_grants: AuthorizationGrantRepository = (
            InMemoryAuthorizationGrantRepository()
        )
        self.jobs: JobRepository = InMemoryJobRepository()
        self.deletion_requests: DeletionRequestRepository = InMemoryDeletionRequestRepository()
        self.audit: AuditPort = InMemoryAuditRepository()
        self.outbox: OutboxPort = InMemoryOutboxRepository()
        self._hooks: list[Any] = []
        self._committed = False
        self._lock = RLock()
        self._actor_kind = "anonymous"
        self._actor_user_id: UUID | None = None

    def __enter__(self) -> InMemoryUnitOfWork:
        # InMemory 实现不重置数据；多次 with 复用同一实例以便测试与
        # Service 共享状态。SQL 实现将创建独立 Session。
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if exc_type is not None:
            self.rollback()

    def commit(self) -> None:
        with self._lock:
            self._committed = True
            hooks = list(self._hooks)
            self._hooks.clear()
        for hook in hooks:
            hook()

    def rollback(self) -> None:
        with self._lock:
            self._hooks.clear()
            # InMemory 没有持久状态，rollback 等价于清空 pending hooks。

    def set_security_context(self, user_id: UUID | None, actor_kind: str) -> None:
        self._actor_kind = actor_kind
        self._actor_user_id = user_id

    def run_after_commit(self, hook: Any) -> None:
        self._hooks.append(hook)

    @property
    def actor_kind(self) -> str:
        return self._actor_kind

    @property
    def actor_user_id(self) -> UUID | None:
        return self._actor_user_id
