"""audit chain heads and approved RBAC constraint

Revision ID: 20260712_0002
Revises: 20260712_0001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260712_0002"
down_revision: str | None = "20260712_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0001 历史迁移从当前 metadata 建表；IF NOT EXISTS 同时兼容既有库与空库升级。
    op.execute(
        "CREATE TABLE IF NOT EXISTS audit.chain_heads ("
        "chain_id varchar(80) PRIMARY KEY, current_hash varchar(64) NOT NULL, "
        "updated_at timestamptz NOT NULL)"
    )
    op.execute(
        "INSERT INTO audit.chain_heads(chain_id, current_hash, updated_at) "
        "VALUES ('identity', 'GENESIS', CURRENT_TIMESTAMP) ON CONFLICT DO NOTHING"
    )
    op.create_check_constraint(
        "ck_identity_users_approved_roles",
        "users",
        "roles <@ ARRAY['USER','ADMIN_OPERATOR']::varchar[] AND roles @> ARRAY['USER']::varchar[]",
        schema="identity",
    )


def downgrade() -> None:
    """仅允许开发空库使用；会破坏审计链并丢失链头。"""
    op.drop_constraint(
        "ck_identity_users_approved_roles", "users", schema="identity", type_="check"
    )
    op.drop_table("chain_heads", schema="audit")
