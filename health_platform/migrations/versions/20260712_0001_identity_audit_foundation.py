"""identity_audit_foundation

Revision ID: 20260712_0001
Revises: None
"""

from collections.abc import Sequence

from alembic import op

from health_platform.modules.audit.adapters import persistence as audit_persistence  # noqa: F401
from health_platform.modules.identity.adapters import (
    persistence as identity_persistence,  # noqa: F401
)
from health_platform.platform.database.core import Base

revision: str = "20260712_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 Identity/Audit 基础、RLS 和追加审计保护。"""
    bind = op.get_bind()
    op.execute("CREATE SCHEMA IF NOT EXISTS identity")
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    Base.metadata.create_all(bind=bind)

    for table in (
        "users",
        "sessions",
        "access_tokens",
        "token_families",
        "refresh_tokens",
        "one_time_tokens",
        "mfa_enrollments",
        "recovery_codes",
        "jobs",
        "security_events",
        "idempotency_records",
    ):
        op.execute(f'ALTER TABLE identity."{table}" ENABLE ROW LEVEL SECURITY')

    # RLS 是第二道防线：普通用户只能访问 app.user_id 对应行；后台/服务身份显式放行。
    user_tables = (
        "users",
        "sessions",
        "access_tokens",
        "token_families",
        "jobs",
        "security_events",
    )
    for table in user_tables:
        column = "id" if table == "users" else "user_id"
        op.execute(
            f'''CREATE POLICY {table}_user_boundary ON identity."{table}"
            USING (
              current_setting('app.actor_kind', true) IN ('background', 'service')
              OR "{column}"::text = current_setting('app.user_id', true)
            )
            WITH CHECK (
              current_setting('app.actor_kind', true) IN ('background', 'service')
              OR "{column}"::text = current_setting('app.user_id', true)
            )'''
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit.reject_event_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit events are append-only';
        END $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit.events
        FOR EACH ROW EXECUTE FUNCTION audit.reject_event_mutation()
        """
    )


def downgrade() -> None:
    """仅用于开发空库回退；生产破坏性迁移必须另行批准。"""
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    op.execute("DROP SCHEMA IF EXISTS audit CASCADE")
    op.execute("DROP SCHEMA IF EXISTS identity CASCADE")
