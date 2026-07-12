"""数据库连接与事务基础。

所属层：Platform / Database。
职责：创建 Engine/SessionFactory、提供显式 UnitOfWork 和事务级 RLS 上下文。
边界：不在导入时连接数据库；Repository 和 Router 均不得 commit。
"""

from collections.abc import Callable
from types import TracebackType
from typing import Self
from uuid import UUID

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Health Platform SQLAlchemy 声明基类。"""


SessionFactory = Callable[[], Session]


def create_database_engine(database_url: str, *, echo: bool = False) -> Engine:
    """创建支持 Kubernetes 多副本和连接健康检查的同步 Engine。"""
    return create_engine(database_url, echo=echo, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """创建不自动 commit/expire 的 Session Factory，事务由 UoW 唯一控制。"""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class SqlAlchemyUnitOfWork:
    """一个写用例一次提交的事务边界。"""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None
        self._committed = False

    def __enter__(self) -> Self:
        """打开独立 Session；调用方须在此范围内构造 Repository。"""
        self.session = self._session_factory()
        return self

    def set_security_context(self, user_id: UUID | None, actor_kind: str) -> None:
        """使用 SET LOCAL 设置 RLS 上下文，使连接归还池后不会泄漏到下一事务。"""
        if self.session is None:
            raise RuntimeError("unit of work is not active")
        self.session.execute(
            text(
                "SELECT set_config('app.user_id', :user_id, true), "
                "set_config('app.actor_kind', :actor_kind, true)"
            ),
            {"user_id": str(user_id) if user_id else "", "actor_kind": actor_kind},
        )

    def commit(self) -> None:
        """提交业务、审计与 Outbox 的同一事务；外部 I/O 必须在返回后执行。"""
        if self.session is None:
            raise RuntimeError("unit of work is not active")
        self.session.commit()
        self._committed = True

    def rollback(self) -> None:
        """回滚当前事务，使审计或 Outbox 写入失败时业务数据也不落库。"""
        if self.session is not None:
            self.session.rollback()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """异常或未显式 commit 时回滚并关闭 Session，清理 RLS 事务上下文。"""
        if self.session is None:
            return
        if exc_type is not None or not self._committed:
            self.session.rollback()
        self.session.close()
