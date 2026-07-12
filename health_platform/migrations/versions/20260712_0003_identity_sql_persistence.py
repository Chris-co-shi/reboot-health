"""identity SQL persistence completion

Revision ID: 20260712_0003
Revises: 20260712_0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260712_0003"
down_revision: str | None = "20260712_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _direct_policy(table: str, column: str = "user_id") -> None:
    op.execute(f'DROP POLICY IF EXISTS {table}_user_boundary ON identity."{table}"')
    op.execute(
        f'''CREATE POLICY {table}_user_boundary ON identity."{table}"
        USING (
          current_setting('app.actor_kind', true) IN ('ADMIN_OPERATOR', 'BACKGROUND')
          OR (current_setting('app.actor_kind', true) = 'USER'
              AND "{column}"::text = current_setting('app.user_id', true))
        )
        WITH CHECK (
          current_setting('app.actor_kind', true) IN ('ADMIN_OPERATOR', 'BACKGROUND')
          OR (current_setting('app.actor_kind', true) = 'USER'
              AND "{column}"::text = current_setting('app.user_id', true))
        )'''
    )


def upgrade() -> None:
    # 0001 历史迁移读取当前 metadata；IF NOT EXISTS 兼容既有库和全新空库。
    op.execute(
        """CREATE TABLE IF NOT EXISTS identity.authorization_grants (
        code_hash varchar(64) PRIMARY KEY,
        user_id uuid NOT NULL,
        client_id varchar(128) NOT NULL,
        redirect_uri text NOT NULL,
        scopes varchar(100)[] NOT NULL,
        nonce varchar(256) NOT NULL,
        code_challenge varchar(128) NOT NULL,
        expires_at timestamptz NOT NULL,
        consumed_at timestamptz NULL)"""
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_identity_authorization_code_hash "
        "ON identity.authorization_grants(code_hash)"
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS identity.deletion_requests (
        id uuid PRIMARY KEY,
        user_id uuid NOT NULL,
        requested_at timestamptz NOT NULL,
        cancelled_at timestamptz NULL,
        completed_at timestamptz NULL)"""
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_identity_deletion_user "
        "ON identity.deletion_requests(user_id)"
    )

    direct = {
        "users": "id",
        "sessions": "user_id",
        "access_tokens": "user_id",
        "token_families": "user_id",
        "one_time_tokens": "user_id",
        "mfa_enrollments": "user_id",
        "jobs": "user_id",
        "security_events": "user_id",
        "authorization_grants": "user_id",
        "deletion_requests": "user_id",
    }
    for table, column in direct.items():
        op.execute(f'ALTER TABLE identity."{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE identity."{table}" FORCE ROW LEVEL SECURITY')
        _direct_policy(table, column)

    for table in ("refresh_tokens", "recovery_codes", "oauth_clients", "idempotency_records"):
        op.execute(f'ALTER TABLE identity."{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE identity."{table}" FORCE ROW LEVEL SECURITY')

    op.execute("DROP POLICY IF EXISTS refresh_tokens_user_boundary ON identity.refresh_tokens")
    op.execute(
        """CREATE POLICY refresh_tokens_user_boundary ON identity.refresh_tokens
        USING (
          current_setting('app.actor_kind', true) IN ('ADMIN_OPERATOR', 'BACKGROUND')
          OR (current_setting('app.actor_kind', true) = 'USER' AND EXISTS (
            SELECT 1 FROM identity.token_families family
            WHERE family.id = refresh_tokens.family_id
              AND family.user_id::text = current_setting('app.user_id', true)))
        ) WITH CHECK (
          current_setting('app.actor_kind', true) IN ('ADMIN_OPERATOR', 'BACKGROUND')
          OR (current_setting('app.actor_kind', true) = 'USER' AND EXISTS (
            SELECT 1 FROM identity.token_families family
            WHERE family.id = refresh_tokens.family_id
              AND family.user_id::text = current_setting('app.user_id', true)))
        )"""
    )
    op.execute("DROP POLICY IF EXISTS recovery_codes_user_boundary ON identity.recovery_codes")
    op.execute(
        """CREATE POLICY recovery_codes_user_boundary ON identity.recovery_codes
        USING (
          current_setting('app.actor_kind', true) IN ('ADMIN_OPERATOR', 'BACKGROUND')
          OR (current_setting('app.actor_kind', true) = 'USER' AND EXISTS (
            SELECT 1 FROM identity.mfa_enrollments enrollment
            WHERE enrollment.id = recovery_codes.enrollment_id
              AND enrollment.user_id::text = current_setting('app.user_id', true)))
        ) WITH CHECK (
          current_setting('app.actor_kind', true) IN ('ADMIN_OPERATOR', 'BACKGROUND')
          OR (current_setting('app.actor_kind', true) = 'USER' AND EXISTS (
            SELECT 1 FROM identity.mfa_enrollments enrollment
            WHERE enrollment.id = recovery_codes.enrollment_id
              AND enrollment.user_id::text = current_setting('app.user_id', true)))
        )"""
    )
    op.execute("DROP POLICY IF EXISTS oauth_clients_internal ON identity.oauth_clients")
    op.execute(
        """CREATE POLICY oauth_clients_read ON identity.oauth_clients FOR SELECT
        USING (current_setting('app.actor_kind', true) IN
          ('USER', 'ADMIN_OPERATOR', 'BACKGROUND'))"""
    )
    op.execute(
        """CREATE POLICY oauth_clients_write ON identity.oauth_clients FOR ALL
        USING (current_setting('app.actor_kind', true) IN ('ADMIN_OPERATOR', 'BACKGROUND'))
        WITH CHECK (current_setting('app.actor_kind', true) IN ('ADMIN_OPERATOR', 'BACKGROUND'))"""
    )
    _direct_policy("idempotency_records")


def downgrade() -> None:
    """仅供开发空库使用；生产回退需独立迁移计划。"""
    for table in (
        "users",
        "sessions",
        "access_tokens",
        "token_families",
        "one_time_tokens",
        "mfa_enrollments",
        "jobs",
        "security_events",
        "idempotency_records",
    ):
        op.execute(f'DROP POLICY IF EXISTS {table}_user_boundary ON identity."{table}"')
    op.execute("DROP POLICY IF EXISTS refresh_tokens_user_boundary ON identity.refresh_tokens")
    op.execute("DROP POLICY IF EXISTS recovery_codes_user_boundary ON identity.recovery_codes")
    op.execute("DROP POLICY IF EXISTS oauth_clients_read ON identity.oauth_clients")
    op.execute("DROP POLICY IF EXISTS oauth_clients_write ON identity.oauth_clients")
    op.drop_table("deletion_requests", schema="identity")
    op.drop_table("authorization_grants", schema="identity")
