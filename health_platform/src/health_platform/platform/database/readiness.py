"""PostgreSQL 与 Alembic readiness 检查，不修改数据库。"""

from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    reason: str | None = None


def check_database_readiness(engine: Engine, alembic_ini: Path) -> ReadinessResult:
    """验证连接和 revision；任何异常只返回稳定分类，不泄露 SQL/地址。"""
    try:
        config = Config(str(alembic_ini))
        script = ScriptDirectory.from_config(config)
        heads = script.get_heads()
        if len(heads) != 1:
            return ReadinessResult(False, "alembic_heads")
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current = MigrationContext.configure(connection).get_current_heads()
        if tuple(current) != tuple(heads):
            return ReadinessResult(False, "database_revision")
        return ReadinessResult(True)
    except Exception:
        return ReadinessResult(False, "database_unavailable")
