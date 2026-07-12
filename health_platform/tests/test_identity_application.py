"""Identity 应用闭环、缓存降级、审计和 Outbox 测试。"""

from datetime import UTC, datetime

import pytest

from health_platform.modules.identity.application.service import (
    IdentityService,
    OAuthClient,
    totp_code,
)
from health_platform.modules.identity.domain.models import IdentityError
from health_platform.platform.encryption.service import (
    AesGcmEncryptionService,
    StaticKeyManagementAdapter,
)
from health_platform.platform.security.passwords import PasswordService


@pytest.fixture
def service() -> IdentityService:
    encryption = AesGcmEncryptionService(StaticKeyManagementAdapter("v1", {"v1": b"x" * 32}))
    return IdentityService(PasswordService(), encryption, "pepper")


def register(service: IdentityService):
    return service.register("alice@example.com", "Alice", "Alice", "correct horse battery staple")


def test_register_writes_audit_and_email_outbox(service: IdentityService) -> None:
    user, token = register(service)
    assert user.id
    assert token
    assert service.state.audits[-1].action == "identity.register"
    assert service.state.outbox[-1].event_type == "identity.email_verification.requested"


def test_new_verification_invalidates_old_token(service: IdentityService) -> None:
    user, old = register(service)
    new = service._create_one_time(user.id, "EMAIL_VERIFICATION", service._access_ttl)
    with pytest.raises(IdentityError):
        service.verify_email(old)
    assert service.verify_email(new).email_verified_at


def test_login_error_does_not_enumerate_user(service: IdentityService) -> None:
    with pytest.raises(IdentityError) as unknown:
        service.login("nobody", "wrong password", "app", "phone", "flutter")
    register(service)
    with pytest.raises(IdentityError) as wrong:
        service.login("alice", "wrong password", "app", "phone", "flutter")
    assert unknown.value.code == wrong.value.code == "IDENTITY_INVALID_CREDENTIALS"


def test_login_refresh_and_replay_revoke_device(service: IdentityService) -> None:
    _, verification = register(service)
    service.verify_email(verification)
    login = service.login("ALICE", "correct horse battery staple", "app", "phone", "flutter")
    refresh = service.refresh(str(login["refresh_token"]))
    assert refresh["refresh_token"] != login["refresh_token"]
    with pytest.raises(IdentityError) as replay:
        service.refresh(str(login["refresh_token"]))
    assert replay.value.code == "IDENTITY_REFRESH_TOKEN_REPLAY"
    with pytest.raises(IdentityError):
        service.authenticate(str(login["access_token"]))


def test_unverified_user_gets_limited_scope(service: IdentityService) -> None:
    register(service)
    tokens = service.login("alice", "correct horse battery staple", "app", "phone", "flutter")
    assert tokens["scope"] == "account:limited"


def test_mfa_enrollment_confirmation_and_recovery_code_reuse(service: IdentityService) -> None:
    user, _ = register(service)
    secret, codes = service.enroll_mfa(user.id)
    now = datetime.now(UTC)
    service.confirm_mfa(user.id, totp_code(secret, now), now)
    service.recover_mfa(user.id, codes[0])
    with pytest.raises(IdentityError):
        service.recover_mfa(user.id, codes[0])


def test_password_reset_revokes_all_sessions(service: IdentityService) -> None:
    _, verification = register(service)
    service.verify_email(verification)
    login = service.login("alice", "correct horse battery staple", "app", "phone", "flutter")
    reset = service.request_password_reset("alice")
    assert reset
    service.complete_password_reset(reset, "a different strong passphrase")
    with pytest.raises(IdentityError):
        service.authenticate(str(login["access_token"]))


def test_password_reset_unknown_identifier_is_ambiguous(service: IdentityService) -> None:
    assert service.request_password_reset("unknown") is None


def test_cross_user_session_revoke_is_blocked(service: IdentityService) -> None:
    register(service)
    tokens = service.login("alice", "correct horse battery staple", "app", "phone", "flutter")
    other = service.register("bob@example.com", "bob", "Bob", "another secure passphrase")[0]
    with pytest.raises(IdentityError) as exc:
        service.revoke_session(
            other.id, service.authenticate(str(tokens["access_token"])).session_id
        )
    assert exc.value.code == "CROSS_USER_ACCESS_DENIED"


def test_deletion_revokes_session_and_enqueues_coordination(service: IdentityService) -> None:
    user, _ = register(service)
    login = service.login("alice", "correct horse battery staple", "app", "phone", "flutter")
    request = service.request_deletion(user.id)
    assert request.ready_at > request.requested_at
    assert service.state.outbox[-1].event_type == "identity.account_deletion.requested"
    with pytest.raises(IdentityError):
        service.authenticate(str(login["access_token"]))


def test_authorization_code_pkce_is_bound_and_one_time(service: IdentityService) -> None:
    from health_platform.platform.security.oauth import pkce_challenge

    user, verification = register(service)
    service.verify_email(verification)
    service.register_oauth_client(OAuthClient("app", ("app://callback",), ("openid",), "api"))
    verifier = "v" * 43
    code = service.authorize(
        user.id,
        "app",
        "app://callback",
        ("openid",),
        "nonce",
        pkce_challenge(verifier),
    )
    tokens, exchanged_user, nonce = service.exchange_authorization_code(
        code, "app", "app://callback", verifier
    )
    assert tokens["access_token"] and exchanged_user.id == user.id and nonce == "nonce"
    with pytest.raises(IdentityError):
        service.exchange_authorization_code(code, "app", "app://callback", verifier)
