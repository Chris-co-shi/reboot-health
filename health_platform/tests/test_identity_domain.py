"""Identity 领域、安全与加密确定性测试。"""

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.exceptions import InvalidTag

from health_platform.modules.audit.domain.models import AuditEvent
from health_platform.modules.identity.application.service import totp_code, verify_totp
from health_platform.modules.identity.domain.models import (
    AccountDeletionRequest,
    IdentityError,
    RecoveryCode,
    Role,
    TokenFamily,
    UserAccount,
    hash_secret,
    normalize_username,
)
from health_platform.platform.encryption.service import (
    AesGcmEncryptionService,
    StaticKeyManagementAdapter,
)
from health_platform.platform.security.oauth import (
    pkce_challenge,
    validate_redirect_uri,
    verify_pkce,
)
from health_platform.platform.security.passwords import PasswordService


def test_user_normalizes_identifiers_and_keeps_display_name() -> None:
    user = UserAccount(" Test@Example.COM ", "Alice", "Alice Zhang", "hash")
    assert user.email == "test@example.com"
    assert user.username == "alice"
    assert user.display_name == "Alice Zhang"


def test_invalid_username_fails_closed() -> None:
    with pytest.raises(IdentityError):
        normalize_username("a")


def test_email_verification_activates_user() -> None:
    user = UserAccount("test@example.com", "alice", "Alice", "hash")
    user.verify_email(datetime(2026, 1, 1, tzinfo=UTC))
    assert user.email_verified_at is not None
    assert user.status.value == "ACTIVE"


def test_login_failures_create_progressive_lock() -> None:
    user = UserAccount("test@example.com", "alice", "Alice", "hash")
    for _ in range(5):
        user.record_login_failure(datetime.now(UTC))
    assert user.locked_until is not None
    with pytest.raises(IdentityError, match="暂时锁定"):
        user.assert_can_login()


def test_token_family_rotates_once_and_detects_replay() -> None:
    user = UserAccount("test@example.com", "alice", "Alice", "hash")
    family = TokenFamily(user.id, user.id)
    expiry = datetime.now(UTC) + timedelta(days=1)
    family.issue_initial("old", expiry)
    family.rotate("old", "new", expiry)
    with pytest.raises(IdentityError) as exc:
        family.rotate("old", "another", expiry)
    assert exc.value.code == "IDENTITY_REFRESH_TOKEN_REPLAY"
    assert family.status.value == "REPLAY_COMPROMISED"


def test_recovery_code_is_one_time() -> None:
    record = RecoveryCode(hash_secret("code"))
    consumed = record.consume(hash_secret("code"))
    with pytest.raises(IdentityError):
        consumed.consume(hash_secret("code"))


def test_deletion_has_seven_day_cooling_period() -> None:
    request = AccountDeletionRequest(user_id=UserAccount("a@b.com", "alice", "A", "h").id)
    assert request.ready_at - request.requested_at == timedelta(days=7)


def test_high_privilege_roles_require_mfa() -> None:
    assert Role.ADMIN_OPERATOR.requires_mfa
    assert not Role.USER.requires_mfa


def test_password_uses_argon2id_and_rejects_common() -> None:
    service = PasswordService()
    hashed = service.hash("a secure long passphrase")
    assert hashed.startswith("$argon2id$")
    assert service.verify(hashed, "a secure long passphrase")
    with pytest.raises(IdentityError):
        service.hash("passwordpassword")


def test_pkce_is_s256_and_redirect_is_exact() -> None:
    verifier = "v" * 43
    challenge = pkce_challenge(verifier)
    assert verify_pkce(verifier, challenge)
    validate_redirect_uri("https://app/callback", ("https://app/callback",))
    with pytest.raises(IdentityError):
        validate_redirect_uri("https://app/callback/evil", ("https://app/callback",))


def test_encryption_is_versioned_and_authenticated() -> None:
    service = AesGcmEncryptionService(
        StaticKeyManagementAdapter("v2", {"v1": b"1" * 32, "v2": b"2" * 32})
    )
    value = service.encrypt("sensitive", b"user")
    assert value.key_version == "v2"
    assert service.decrypt(value, b"user") == "sensitive"
    with pytest.raises(InvalidTag):
        service.decrypt(value, b"other")


def test_totp_accepts_current_code() -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    secret = "JBSWY3DPEHPK3PXP"
    assert verify_totp(secret, totp_code(secret, at), at)


def test_audit_hash_chain_changes_with_previous_hash() -> None:
    first = AuditEvent("USER", "login", "user", "SUCCESS")
    second = AuditEvent("USER", "login", "user", "SUCCESS", previous_hash=first.event_hash)
    assert first.event_hash != second.event_hash
