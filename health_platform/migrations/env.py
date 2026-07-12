"""Health Platform 单一 Alembic 环境。

只加载 SQLAlchemy metadata，不读取业务 Secret 或启动应用后台线程。
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from health_platform.modules.audit.adapters import persistence as audit_persistence  # noqa: F401
from health_platform.modules.identity.adapters import (
    persistence as identity_persistence,  # noqa: F401
)
from health_platform.platform.database.core import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """以 SQL 输出模式运行迁移。"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """使用独立连接运行迁移；生产由单实例 Migration Job 调用。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
