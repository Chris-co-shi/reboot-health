"""SQL Mapper、生产配置门禁与 readiness 的非数据库测试。"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from health_platform.modules.identity.adapters.persistence import (
    AccessTokenRow,
    AuthorizationGrantRow,
    DeletionRequestRow,
    IdentityJobRow,
    OAuthClientRow,
    OneTimeTokenRow,
    RefreshTokenRow,
    SessionRow,
    SqlAccessGrantRepository,
    SqlAuthorizationGrantRepository,
    SqlDeletionRequestRepository,
    SqlJobRepository,
    SqlOAuthClientRepository,
    SqlOneTimeTokenRepository,
    SqlRefreshTokenRepository,
    SqlSessionRepository,
    SqlUserRepository,
    UserRow,
)
from health_platform.modules.identity.application.ports import (
    AccessGrant,
    AuthorizationGrant,
    IdentityJob,
    OAuthClient,
    OneTimeGrant,
)
from health_platform.modules.identity.domain.models import (
    AccountDeletionRequest,
    IdentityError,
    IdentitySession,
    RefreshTokenRecord,
    UserAccount,
)
from health_platform.platform.configuration.settings import Settings
from health_platform.platform.database.readiness import ReadinessResult, check_database_readiness
from health_platform.platform.web.app import create_app


def test_mapper_round_trips_preserve_all_fields() -> None:
    now = datetime.now(UTC)
    user_id, session_id = uuid4(), uuid4()
    user = UserAccount("mapper@example.com", "mapper", "Mapper", "hash", id=user_id)
    user_row = SqlUserRepository.to_row(user)
    assert SqlUserRepository.to_domain(user_row) == user
    session = IdentitySession(user_id, "client", "phone", "flutter", id=session_id)
    session_row = SqlSessionRepository.to_row(session)
    assert isinstance(session_row, SessionRow)
    assert SqlSessionRepository.to_domain(session_row) == session

    access = AccessGrant("a" * 64, user_id, session_id, "client", "api", ("read",), 2, now)
    access_row = SqlAccessGrantRepository.to_row(access)
    assert isinstance(access_row, AccessTokenRow)
    assert SqlAccessGrantRepository.to_domain(access_row) == access

    refresh = RefreshTokenRecord("r" * 64, now + timedelta(days=1))
    refresh_row = SqlRefreshTokenRepository.to_row(uuid4(), refresh)
    assert isinstance(refresh_row, RefreshTokenRow)
    assert SqlRefreshTokenRepository.to_domain(refresh_row) == refresh

    one_time = OneTimeGrant(user_id, "VERIFY", "o" * 64, now, {"key": "value"})
    one_time_row = SqlOneTimeTokenRepository.to_row(one_time)
    assert isinstance(one_time_row, OneTimeTokenRow)
    assert SqlOneTimeTokenRepository.to_domain(one_time_row) == one_time

    client = OAuthClient("client", ("app://callback",), ("openid",), "api")
    client_row = SqlOAuthClientRepository.to_row(client)
    assert isinstance(client_row, OAuthClientRow)
    assert SqlOAuthClientRepository.to_domain(client_row) == client

    authorization = AuthorizationGrant(
        user_id, "client", "app://callback", ("openid",), "nonce", "challenge", now
    )
    authorization_row = SqlAuthorizationGrantRepository.to_row("c" * 64, authorization)
    assert isinstance(authorization_row, AuthorizationGrantRow)
    assert SqlAuthorizationGrantRepository.to_domain(authorization_row) == authorization

    job = IdentityJob(uuid4(), user_id, "export", "PENDING", {"scope": "identity"}, now)
    job_row = SqlJobRepository.to_row(job)
    assert isinstance(job_row, IdentityJobRow)
    assert SqlJobRepository.to_domain(job_row) == job

    deletion = AccountDeletionRequest(user_id, now)
    deletion_row = SqlDeletionRequestRepository.to_row(deletion)
    assert isinstance(deletion_row, DeletionRequestRow)
    assert SqlDeletionRequestRepository.to_domain(deletion_row) == deletion


def test_unknown_database_role_fails_closed() -> None:
    now = datetime.now(UTC)
    row = UserRow(
        id=uuid4(),
        email_normalized="role@example.com",
        username_normalized="role-user",
        display_name="Role",
        password_hash="hash",
        status="ACTIVE",
        permission_version=1,
        failed_login_count=0,
        roles=["UNKNOWN"],
        created_at=now,
        updated_at=now,
    )
    with pytest.raises(IdentityError) as error:
        SqlUserRepository.to_domain(row)
    assert error.value.code == "IDENTITY_UNKNOWN_ROLE"


def test_production_settings_fail_closed_when_persistence_config_missing() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")


def test_production_default_attempts_sql_not_in_memory(monkeypatch, tmp_path) -> None:
    def stop_at_engine(database_url: str):
        raise RuntimeError("sql-engine-selected")

    monkeypatch.setattr("health_platform.platform.web.app.create_database_engine", stop_at_engine)
    settings = Settings(
        environment="production",
        database_url="postgresql+psycopg://test:test@localhost/test",
        token_pepper="explicit-pepper",
        encryption_key_file=str(tmp_path / "encryption.json"),
        encryption_current_key_version="v1",
        oidc_private_key_file=str(tmp_path / "oidc.pem"),
        oauth_first_party_client_id="client",
        oauth_first_party_redirect_uris=("app://callback",),
    )
    with pytest.raises(RuntimeError, match="sql-engine-selected"):
        create_app(settings=settings)


def test_readiness_failure_is_sanitized() -> None:
    app = create_app(readiness_check=lambda: ReadinessResult(False, "database_revision"))
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "reason": "database_revision"}


def test_readiness_rejects_multiple_code_heads(monkeypatch, tmp_path) -> None:
    class MultipleHeads:
        def get_heads(self):
            return ["head-a", "head-b"]

    monkeypatch.setattr(
        "health_platform.platform.database.readiness.ScriptDirectory.from_config",
        lambda config: MultipleHeads(),
    )
    result = check_database_readiness(object(), tmp_path / "alembic.ini")
    assert not result.ready and result.reason == "alembic_heads"
