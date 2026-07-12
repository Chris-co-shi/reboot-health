from uuid import uuid4

import pytest

from health_platform.modules.identity.application.policy import (
    Principal,
    require_admin_operator,
    require_scope,
    require_self,
    require_service_health_agent,
)
from health_platform.modules.identity.domain.models import (
    ActorKind,
    IdentityError,
    Role,
    UserAccount,
)


def test_user_defaults_to_user_and_service_role_cannot_be_assigned() -> None:
    user = UserAccount("user@example.com", "user_name", "User", "hash")
    assert user.roles == {Role.USER}
    assert {role.value for role in Role} == {"USER", "ADMIN_OPERATOR"}


def test_admin_role_changes_are_idempotent_and_increment_permission_version() -> None:
    user = UserAccount("admin@example.com", "admin_user", "Admin", "hash")
    assert user.grant_admin_operator()
    assert user.permission_version == 2
    assert not user.grant_admin_operator()
    assert user.permission_version == 2
    assert user.revoke_admin_operator()
    assert user.permission_version == 3
    assert not user.revoke_admin_operator()


def test_policy_fails_closed_for_unknown_scope_and_cross_user() -> None:
    user_id = uuid4()
    principal = Principal(
        subject_id=str(user_id),
        actor_kind=ActorKind.USER,
        user_id=user_id,
        roles=frozenset({Role.USER}),
        scopes=frozenset({"account:read"}),
    )
    with pytest.raises(IdentityError, match="权限不足"):
        require_scope(principal, "unknown:scope", frozenset({"account:read"}))
    with pytest.raises(IdentityError) as error:
        require_self(principal, uuid4())
    assert error.value.code == "CROSS_USER_ACCESS_DENIED"


def test_admin_requires_mfa_and_service_is_not_human_user() -> None:
    admin_id = uuid4()
    admin = Principal(
        subject_id=str(admin_id),
        actor_kind=ActorKind.ADMIN_OPERATOR,
        user_id=admin_id,
        roles=frozenset({Role.USER, Role.ADMIN_OPERATOR}),
    )
    with pytest.raises(IdentityError):
        require_admin_operator(admin, mfa_enabled=False)
    require_admin_operator(admin, mfa_enabled=True)

    service = Principal(
        subject_id="health-agent",
        actor_kind=ActorKind.SERVICE_HEALTH_AGENT,
        scopes=frozenset({"agent:invoke"}),
        audience="health-platform",
    )
    require_service_health_agent(service)
    with pytest.raises(IdentityError):
        require_admin_operator(service, mfa_enabled=True)
