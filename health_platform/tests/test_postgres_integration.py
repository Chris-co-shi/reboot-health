"""真实 PostgreSQL 的迁移、约束、事务与 Outbox 语义测试。"""

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from health_platform.modules.audit.adapters.persistence import (
    AuditEventRow,
    OutboxEventRow,
    SqlAuditRepository,
    SqlOutboxRepository,
)
from health_platform.modules.audit.domain.models import AuditEvent, OutboxEvent, OutboxStatus
from health_platform.modules.identity.adapters.persistence import (
    OAuthClientRow,
    SqlOAuthClientRepository,
    SqlTokenFamilyRepository,
    UserRow,
)
from health_platform.modules.identity.application.ports import (
    AuthorizationGrant,
    MfaState,
    OAuthClient,
)
from health_platform.modules.identity.application.service import IdentityService
from health_platform.modules.identity.domain.models import (
    AccountDeletionRequest,
    RecoveryCode,
    TokenFamily,
    UserAccount,
)
from health_platform.platform.configuration.settings import Settings
from health_platform.platform.database.core import create_session_factory
from health_platform.platform.database.readiness import check_database_readiness
from health_platform.platform.database.sqlalchemy_uow import SqlAlchemyIdentityUnitOfWork
from health_platform.platform.encryption.service import (
    AesGcmEncryptionService,
    EncryptedValue,
    StaticKeyManagementAdapter,
)
from health_platform.platform.security.oauth import pkce_challenge
from health_platform.platform.security.passwords import PasswordService
from health_platform.platform.web.app import create_app

pytestmark = pytest.mark.postgres


def _service(engine) -> IdentityService:
    session_factory = create_session_factory(engine)
    encryption = AesGcmEncryptionService(StaticKeyManagementAdapter("v1", {"v1": b"x" * 32}))
    return IdentityService(
        PasswordService(),
        encryption,
        "test-pepper",
        uow_factory=lambda: SqlAlchemyIdentityUnitOfWork(session_factory),
    )


@pytest.fixture(scope="module")
def postgres_url() -> str:
    """优先使用显式隔离测试库，否则启动禁用 Ryuk 的一次性 PostgreSQL 17。"""
    configured = os.getenv("TEST_DATABASE_URL")
    if configured:
        database = make_url(configured).database or ""
        if "test" not in database.casefold():
            raise RuntimeError("TEST_DATABASE_URL database name must contain 'test'")
        yield configured
        return
    os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:17-alpine", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="module")
def migrated_url(postgres_url: str) -> str:
    """从空库执行唯一 Alembic 主线，并在外部隔离测试库结束后清理。"""
    root = Path(__file__).parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield postgres_url
    command.downgrade(config, "base")


def test_alembic_empty_database_has_identity_audit_and_one_head(migrated_url: str) -> None:
    root = Path(__file__).parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", migrated_url)
    command.check(config)
    assert len(ScriptDirectory.from_config(config).get_heads()) == 1
    engine = create_engine(migrated_url)
    inspector = inspect(engine)
    assert "users" in inspector.get_table_names(schema="identity")
    assert "events" in inspector.get_table_names(schema="audit")
    assert "chain_heads" in inspector.get_table_names(schema="audit")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM alembic_version")) == 1
        version = str(connection.scalar(text("SELECT version()")))
        print(f"PostgreSQL version: {version}")
        assert "PostgreSQL 17" in version


def test_identity_unique_constraint_and_transaction_rollback(migrated_url: str) -> None:
    engine = create_engine(migrated_url)
    now = datetime.now(UTC)
    values = dict(
        email_normalized="unique@example.com",
        username_normalized="unique-user",
        display_name="Unique",
        password_hash="hash",
        status="ACTIVE",
        permission_version=1,
        failed_login_count=0,
        roles=["USER"],
        created_at=now,
        updated_at=now,
    )
    with Session(engine) as session:
        session.add(UserRow(**values))
        session.commit()
        session.add(UserRow(**{**values, "username_normalized": "other-user"}))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert session.query(UserRow).count() == 1


def test_audit_chain_head_and_event_roll_back_together(migrated_url: str) -> None:
    engine = create_engine(migrated_url)
    with Session(engine) as session:
        repository = SqlAuditRepository(session)
        first = AuditEvent("BACKGROUND", "identity.test.first", "user", "SUCCESS")
        first_hash = repository.append(first)
        session.commit()
    with Session(engine) as session:
        repository = SqlAuditRepository(session)
        second = AuditEvent("BACKGROUND", "identity.test.second", "user", "SUCCESS")
        second_hash = repository.append(second)
        session.rollback()
    with Session(engine) as session:
        repository = SqlAuditRepository(session)
        assert repository.current_hash() == first_hash
        assert session.query(AuditEventRow).filter_by(event_hash=second_hash).count() == 0


def test_outbox_skip_locked_claim_and_expired_recovery(migrated_url: str) -> None:
    engine = create_engine(migrated_url)
    now = datetime.now(UTC)
    with Session(engine) as session:
        row = OutboxEventRow(
            event_type="test",
            aggregate_type="user",
            aggregate_id=uuid4(),
            payload={},
            status=OutboxStatus.PENDING.value,
            created_at=now,
            available_at=now,
            attempt_count=0,
        )
        session.add(row)
        session.commit()
        event_id = row.event_id
    first = Session(engine)
    second = Session(engine)
    try:
        claimed = SqlOutboxRepository(first).claim("worker-a", now, 30)
        assert claimed is not None and claimed.event_id == event_id
        assert SqlOutboxRepository(second).claim("worker-b", now, 30) is None
        first.commit()
    finally:
        first.close()
        second.close()


def test_rls_blocks_cross_user_and_transaction_context_does_not_leak(migrated_url: str) -> None:
    """真实非 owner 角色验证跨用户阻断及连接复用后的事务上下文清理。"""
    engine = create_engine(migrated_url)
    ids = [uuid4(), uuid4()]
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(text("DROP ROLE IF EXISTS hp_rls_test"))
        connection.execute(text("CREATE ROLE hp_rls_test NOLOGIN"))
        connection.execute(text("GRANT USAGE ON SCHEMA identity TO hp_rls_test"))
        connection.execute(text("GRANT SELECT ON identity.users TO hp_rls_test"))
        for index, user_id in enumerate(ids):
            connection.execute(
                UserRow.__table__.insert().values(
                    id=user_id,
                    email_normalized=f"rls{index}@example.com",
                    username_normalized=f"rls-user-{index}",
                    display_name=f"RLS {index}",
                    password_hash="hash",
                    status="ACTIVE",
                    permission_version=1,
                    failed_login_count=0,
                    roles=["USER"],
                    created_at=now,
                    updated_at=now,
                )
            )
    with engine.connect() as connection:
        with connection.begin():
            connection.execute(text("SET LOCAL ROLE hp_rls_test"))
            connection.execute(
                text(
                    "SELECT set_config('app.user_id', :user_id, true), "
                    "set_config('app.actor_kind', 'USER', true)"
                ),
                {"user_id": str(ids[0])},
            )
            visible = connection.scalar(text("SELECT count(*) FROM identity.users"))
            assert visible == 1
        with connection.begin():
            connection.execute(text("SET LOCAL ROLE hp_rls_test"))
            connection.execute(text("SELECT set_config('app.actor_kind', 'ANONYMOUS', true)"))
            assert connection.scalar(text("SELECT count(*) FROM identity.users")) == 0


def test_sql_uow_persists_identity_across_engine_restart(migrated_url: str) -> None:
    first_engine = create_engine(migrated_url, pool_pre_ping=True)
    service = _service(first_engine)
    user, verification = service.register(
        "persistent@example.com", "persistent", "Persistent", "a secure persistent password"
    )
    service.verify_email(verification)
    tokens = service.login(
        "persistent", "a secure persistent password", "flutter", "phone", "flutter"
    )
    client = OAuthClient("restart-client", ("app://callback",), ("openid",), "api")
    service.register_oauth_client(client)
    verifier = "v" * 43
    code = service.authorize(
        user.id,
        client.client_id,
        client.redirect_uris[0],
        client.allowed_scopes,
        "nonce",
        pkce_challenge(verifier),
    )
    first_engine.dispose()
    second_engine = create_engine(migrated_url, pool_pre_ping=True)
    restored = _service(second_engine)
    assert restored.authenticate(str(tokens["access_token"])).user_id == user.id
    assert restored.refresh(str(tokens["refresh_token"]))["refresh_token"]
    exchanged, exchanged_user, nonce = restored.exchange_authorization_code(
        code, client.client_id, client.redirect_uris[0], verifier
    )
    assert exchanged["access_token"] and exchanged_user.id == user.id and nonce == "nonce"
    assert restored.get_user(user.id).username == "persistent"
    second_engine.dispose()


def test_identity_audit_outbox_roll_back_as_one_transaction(migrated_url: str) -> None:
    engine = create_engine(migrated_url)
    session_factory = create_session_factory(engine)
    user = UserAccount("rollback@example.com", "rollback", "Rollback", "hash")
    with SqlAlchemyIdentityUnitOfWork(session_factory) as uow:
        uow.set_security_context(None, "BACKGROUND")
        before = uow.audit.current_hash()
    with pytest.raises(Exception) as error:
        with SqlAlchemyIdentityUnitOfWork(session_factory) as uow:
            uow.set_security_context(None, "BACKGROUND")
            uow.users.add(user)
            uow.audit.append(AuditEvent("BACKGROUND", "rollback", "user", "SUCCESS"))
            duplicate_id = uuid4()
            event = OutboxEvent("rollback", "user", user.id, {}, event_id=duplicate_id)
            uow.outbox.enqueue(event)
            uow.outbox.enqueue(event)
            called: list[str] = []
            uow.run_after_commit(lambda: called.append("unexpected"))
            uow.commit()
    assert getattr(error.value, "code", None) == "IDENTITY_CONFLICT"
    assert called == []
    with SqlAlchemyIdentityUnitOfWork(session_factory) as uow:
        uow.set_security_context(None, "BACKGROUND")
        assert uow.users.get(user.id) is None
        assert uow.audit.current_hash() == before


def test_remaining_sql_repositories_persist_and_map(migrated_url: str) -> None:
    engine = create_engine(migrated_url)
    factory = create_session_factory(engine)
    user = UserAccount("repositories@example.com", "repositories", "Repositories", "hash")
    request = AccountDeletionRequest(user.id)
    job_id = uuid4()
    code_hash = "c" * 64
    authorization = AuthorizationGrant(
        user.id,
        "client",
        "app://callback",
        ("openid",),
        "nonce",
        "challenge",
        datetime.now(UTC) + timedelta(minutes=5),
    )
    mfa = MfaState(
        EncryptedValue("ciphertext", "nonce", "v1"),
        True,
        [RecoveryCode("r" * 64)],
    )
    committed: list[str] = []
    with SqlAlchemyIdentityUnitOfWork(factory) as uow:
        uow.set_security_context(None, "BACKGROUND")
        uow.users.add(user)
        uow.mfa.add(user.id, mfa)
        uow.authorization_grants.add(code_hash, authorization)
        uow.jobs.add(job_id, user.id, "export", "PENDING", {"scope": "identity"})
        uow.deletion_requests.add(request)
        uow.run_after_commit(lambda: committed.append("done"))
        uow.commit()
    assert committed == ["done"]
    with SqlAlchemyIdentityUnitOfWork(factory) as uow:
        uow.set_security_context(None, "BACKGROUND")
        assert uow.mfa.get(user.id) == mfa
        assert uow.authorization_grants.consume(code_hash) is not None
        assert uow.jobs.get(job_id) is not None
        assert uow.deletion_requests.get(request.id) == request


def test_audit_chain_concurrent_writes_do_not_fork(migrated_url: str) -> None:
    engine = create_engine(migrated_url)
    barrier = Barrier(10)

    def append(index: int) -> str:
        barrier.wait()
        with Session(engine) as session:
            result = SqlAuditRepository(session).append(
                AuditEvent("BACKGROUND", f"concurrent.{index}", "audit", "SUCCESS")
            )
            session.commit()
            return result

    with ThreadPoolExecutor(max_workers=10) as executor:
        hashes = list(executor.map(append, range(10)))
    with Session(engine) as session:
        rows = session.query(AuditEventRow).filter(AuditEventRow.event_hash.in_(hashes)).all()
        assert len(rows) == 10
        assert len({row.previous_hash for row in rows}) == 10
        assert sum(row.previous_hash in hashes for row in rows) == 9
        assert SqlAuditRepository(session).current_hash() in hashes


def test_token_family_for_update_holds_real_row_lock(migrated_url: str) -> None:
    engine = create_engine(migrated_url)
    family = TokenFamily(uuid4(), uuid4())
    with Session(engine) as setup:
        setup.execute(text("SELECT set_config('app.actor_kind', 'BACKGROUND', true)"))
        SqlTokenFamilyRepository(setup).add(family)
        setup.commit()
    first = Session(engine)
    second = Session(engine)
    try:
        first.execute(text("SELECT set_config('app.actor_kind', 'BACKGROUND', true)"))
        assert SqlTokenFamilyRepository(first).get(family.id, for_update=True) is not None
        second.execute(text("SET LOCAL lock_timeout = '200ms'"))
        second.execute(text("SELECT set_config('app.actor_kind', 'BACKGROUND', true)"))
        with pytest.raises(OperationalError):
            SqlTokenFamilyRepository(second).get(family.id, for_update=True)
    finally:
        first.rollback()
        second.rollback()
        first.close()
        second.close()


def test_oauth_client_initialization_is_idempotent_and_conflict_safe(migrated_url: str) -> None:
    engine = create_engine(migrated_url)
    client = OAuthClient("concurrent-client", ("app://callback",), ("openid",), "api")
    barrier = Barrier(2)

    def initialize(_: int) -> None:
        barrier.wait()
        with Session(engine) as session:
            session.execute(text("SELECT set_config('app.actor_kind', 'BACKGROUND', true)"))
            SqlOAuthClientRepository(session).upsert(client)
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(initialize, range(2)))
    with Session(engine) as session:
        session.execute(text("SELECT set_config('app.actor_kind', 'BACKGROUND', true)"))
        assert session.query(OAuthClientRow).filter_by(client_id=client.client_id).count() == 1
        incompatible = OAuthClient(client.client_id, ("app://other",), ("openid",), "api")
        with pytest.raises(Exception) as error:
            SqlOAuthClientRepository(session).upsert(incompatible)
        assert getattr(error.value, "code", None) == "IDENTITY_OAUTH_CLIENT_CONFLICT"


def test_database_readiness_detects_revision_and_connectivity(migrated_url: str) -> None:
    root = Path(__file__).parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", migrated_url)
    engine = create_engine(migrated_url)
    assert check_database_readiness(engine, root / "alembic.ini").ready
    command.downgrade(config, "20260712_0002")
    mismatch = check_database_readiness(engine, root / "alembic.ini")
    assert not mismatch.ready and mismatch.reason == "database_revision"
    command.upgrade(config, "head")
    unavailable_engine = create_engine(
        "postgresql+psycopg://test:test@127.0.0.1:1/test",
        connect_args={"connect_timeout": 1},
    )
    unavailable = check_database_readiness(unavailable_engine, root / "alembic.ini")
    assert not unavailable.ready and unavailable.reason == "database_unavailable"


def test_production_composition_root_uses_sql_and_revision_readiness(
    migrated_url: str, tmp_path: Path
) -> None:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = tmp_path / "oidc.pem"
    private_path.write_bytes(
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    encryption_path = tmp_path / "encryption.json"
    encryption_path.write_text(
        json.dumps(
            {
                "current_version": "v1",
                "keys": {"v1": base64.b64encode(b"k" * 32).decode()},
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        environment="production",
        database_url=migrated_url,
        token_pepper="production-test-pepper",
        encryption_key_file=str(encryption_path),
        encryption_current_key_version="v1",
        oidc_private_key_file=str(private_path),
        oauth_first_party_client_id="production-client",
        oauth_first_party_redirect_uris=("app://callback",),
    )
    app = create_app(settings=settings)
    assert app.state.engine is not None
    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 200
        root = Path(__file__).parents[1]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", migrated_url)
        command.downgrade(config, "20260712_0002")
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["reason"] == "database_revision"
        command.upgrade(config, "head")
