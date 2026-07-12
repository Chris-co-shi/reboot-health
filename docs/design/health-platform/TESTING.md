# 测试设计

pytest 分为 domain、application、api/security 与 PostgreSQL integration。单元测试不访问公网；数据库语义只用 Testcontainers PostgreSQL，不以 SQLite 替代。

覆盖状态机、Token Rotation/Replay、MFA、验证/恢复、锁定/删除冷静期、审计链、事务同写、缓存降级、PKCE/JWKS、错误脱敏。集成测试覆盖 Alembic、约束、回滚、RLS、连接复用、`SKIP LOCKED`、并发轮换和审计追加约束。

CI 执行 uv frozen sync、Ruff、Mypy、pytest/cov、Alembic、Bandit、pip-audit 与 health-agent 回归。
