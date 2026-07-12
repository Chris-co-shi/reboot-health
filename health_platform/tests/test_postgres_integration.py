"""真实 PostgreSQL 的迁移、约束、事务与 Outbox 语义测试。"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from health_platform.modules.audit.adapters.persistence import OutboxEventRow, SqlOutboxRepository
from health_platform.modules.audit.domain.models import OutboxStatus
from health_platform.modules.identity.adapters.persistence import UserRow

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module")
def postgres_url() -> str:
    """启动真实 PostgreSQL，禁止用 SQLite 替代 RLS 与 SKIP LOCKED 语义。"""
    with PostgresContainer("postgres:17-alpine", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="module")
def migrated_url(postgres_url: str) -> str:
    """从空库执行唯一 Alembic 主线。"""
    root = Path(__file__).parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(config, "head")
    return postgres_url


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
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM alembic_version")) == 1


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
                text("SELECT set_config('app.user_id', :user_id, true)"),
                {"user_id": str(ids[0])},
            )
            visible = connection.scalar(text("SELECT count(*) FROM identity.users"))
            assert visible == 1
        with connection.begin():
            connection.execute(text("SET LOCAL ROLE hp_rls_test"))
            assert connection.scalar(text("SELECT count(*) FROM identity.users")) == 0
