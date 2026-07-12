"""生产 Identity SQLAlchemy Unit of Work。"""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from health_platform.modules.audit.adapters.persistence import (
    SqlAuditRepository,
    SqlOutboxRepository,
)
from health_platform.modules.identity.adapters.persistence import (
    SqlAccessGrantRepository,
    SqlAuthorizationGrantRepository,
    SqlDeletionRequestRepository,
    SqlJobRepository,
    SqlMfaRepository,
    SqlOAuthClientRepository,
    SqlOneTimeTokenRepository,
    SqlRefreshTokenRepository,
    SqlSessionRepository,
    SqlTokenFamilyRepository,
    SqlUserRepository,
)
from health_platform.modules.identity.application.ports import (
    AccessGrantRepository,
    AuditPort,
    AuthorizationGrantRepository,
    DeletionRequestRepository,
    IdentityUnitOfWork,
    JobRepository,
    MfaRepository,
    OAuthClientRepository,
    OneTimeTokenRepository,
    OutboxPort,
    RefreshTokenRepository,
    SessionRepository,
    TokenFamilyRepository,
    UserRepository,
)
from health_platform.modules.identity.domain.models import IdentityError


class SqlAlchemyIdentityUnitOfWork(IdentityUnitOfWork):
    """一个 UoW 对应一个 Session 和一个 PostgreSQL 事务。"""

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

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._hooks: list[Callable[[], object]] = []
        self._committed = False

    def __enter__(self) -> IdentityUnitOfWork:
        session = self._session_factory()
        self._session = session
        self.users = SqlUserRepository(session)
        self.sessions = SqlSessionRepository(session)
        self.access_grants = SqlAccessGrantRepository(session)
        self.token_families = SqlTokenFamilyRepository(session)
        self.refresh_tokens = SqlRefreshTokenRepository(session)
        self.one_time_tokens = SqlOneTimeTokenRepository(session)
        self.mfa = SqlMfaRepository(session)
        self.oauth_clients = SqlOAuthClientRepository(session)
        self.authorization_grants = SqlAuthorizationGrantRepository(session)
        self.jobs = SqlJobRepository(session)
        self.deletion_requests = SqlDeletionRequestRepository(session)
        self.audit = SqlAuditRepository(session)
        self.outbox = SqlOutboxRepository(session)
        return self

    def set_security_context(self, user_id: UUID | None, actor_kind: str) -> None:
        session = self._require_session()
        normalized = actor_kind.upper()
        if normalized == "USER" and user_id is None:
            normalized = "BACKGROUND"
        if normalized not in {"USER", "ADMIN_OPERATOR", "BACKGROUND", "ANONYMOUS"}:
            raise IdentityError("IDENTITY_UNKNOWN_ACTOR_KIND", "主体类型无效")
        session.execute(
            text(
                "SELECT set_config('app.user_id', :user_id, true), "
                "set_config('app.actor_kind', :actor_kind, true)"
            ),
            {"user_id": str(user_id) if user_id else "", "actor_kind": normalized},
        )

    def commit(self) -> None:
        session = self._require_session()
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            self._hooks.clear()
            raise IdentityError("IDENTITY_CONFLICT", "Identity 资源冲突") from exc
        self._committed = True
        hooks, self._hooks = self._hooks, []
        for hook in hooks:
            hook()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()
        self._hooks.clear()

    def run_after_commit(self, hook: Callable[[], object]) -> None:
        self._hooks.append(hook)

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        if self._session is None:
            return
        if exc_type is not None or not self._committed:
            self.rollback()
        self._session.close()
        self._session = None

    def _require_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        return self._session
