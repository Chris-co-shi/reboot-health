"""确定性 Principal 与授权 Policy；所有未知值默认拒绝。"""

from dataclasses import dataclass
from uuid import UUID

from health_platform.modules.identity.domain.models import ActorKind, IdentityError, Role


@dataclass(frozen=True)
class Principal:
    subject_id: str
    actor_kind: ActorKind
    user_id: UUID | None = None
    session_id: UUID | None = None
    client_id: str | None = None
    roles: frozenset[Role] = frozenset()
    scopes: frozenset[str] = frozenset()
    audience: str = ""
    permission_version: int = 0
    mfa_authenticated: bool = False


def _deny() -> None:
    raise IdentityError("AUTHORIZATION_DENIED", "权限不足")


def require_authenticated(principal: Principal) -> None:
    if principal.actor_kind is ActorKind.ANONYMOUS:
        raise IdentityError("AUTHENTICATION_REQUIRED", "需要登录")


def require_human_user(principal: Principal) -> None:
    require_authenticated(principal)
    if (
        principal.actor_kind not in {ActorKind.USER, ActorKind.ADMIN_OPERATOR}
        or principal.user_id is None
    ):
        _deny()


def require_mfa(principal: Principal) -> None:
    require_authenticated(principal)
    if not principal.mfa_authenticated:
        _deny()


def require_admin_operator(principal: Principal) -> None:
    require_human_user(principal)
    if (
        principal.actor_kind is not ActorKind.ADMIN_OPERATOR
        or Role.ADMIN_OPERATOR not in principal.roles
    ):
        _deny()
    require_mfa(principal)


def require_service_health_agent(principal: Principal) -> None:
    require_authenticated(principal)
    if principal.actor_kind is not ActorKind.SERVICE_HEALTH_AGENT or principal.user_id is not None:
        _deny()


def require_scope(principal: Principal, scope: str, known_scopes: frozenset[str]) -> None:
    if scope not in known_scopes or scope not in principal.scopes:
        _deny()


def require_audience(principal: Principal, audience: str) -> None:
    if not audience or principal.audience != audience:
        _deny()


def require_self(principal: Principal, resource_user_id: UUID) -> None:
    require_human_user(principal)
    if principal.user_id != resource_user_id:
        raise IdentityError("CROSS_USER_ACCESS_DENIED", "禁止跨用户访问")


def require_self_or_admin(principal: Principal, resource_user_id: UUID) -> None:
    if principal.user_id == resource_user_id:
        require_human_user(principal)
        return
    require_admin_operator(principal)
