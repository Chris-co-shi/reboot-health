# 0019 Health Platform 持久化与事务

## 状态

已确认，2026-07-12 生效。

## Context

身份、审计、Outbox、幂等和跨 Pod 抢占需要同一权威事务与真实 PostgreSQL 语义。

## Decision

采用 SQLAlchemy 2 同步 Session、psycopg 3、单一 PostgreSQL 和一条 Alembic 主线。业务模块使用独立 Schema；写用例通过 Unit of Work 一次提交，Repository 不提交。关键审计和 Outbox 与业务数据同事务写入。远程 I/O 只在提交后执行。RLS 作为 Application 授权后的第二道防线，事务级设置并在连接归还前清理。

## Alternatives

- SQLite：缺少 RLS、`SKIP LOCKED` 和 PostgreSQL 并发语义。
- 每模块数据库：增加分布式一致性成本。
- 启动时自动建表：生产变更不可审计、不可回滚。

## Consequences

需要 Alembic、真实 PostgreSQL 集成测试和模型漂移检查；跨模块外键默认禁止。

## Security impact

Schema 权限、RLS、事务级安全上下文和追加审计形成纵深防御；连接池复用必须测试上下文清理。

## Migration impact

所有变更经 Alembic，重大变更采用 expand → migrate → contract；不导入旧 Flyway 历史。

## Superseded relationship

扩展 ADR 0013 的 PostgreSQL 权威与 Outbox 语义，不改变 health-agent 独立数据库边界。

## Validation

空库升级、单一 Head、唯一约束、回滚、RLS、并发轮换、Outbox 抢占与 Alembic check。
