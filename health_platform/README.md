# Python Health Platform

`health_platform/` 是 reboot-health 的业务平台、数据权威和控制面。它管理用户身份与业务权限，以及 Conversation、Fact、Plan、Risk、File、Secret 和业务审计。

微信小程序、Flutter 和 Vue Admin 只能访问 Health Platform。Health Platform 通过内部 HTTPS、mTLS 和短期 JWT 调用 `health-agent`；`health-agent` 不得直接连接 Platform 数据库。

Phase 3B Slice 2 已建立 FastAPI、Identity 领域/API 基础、SQLAlchemy/Alembic、Audit/Outbox、缓存/加密/邮件适配器、后台线程和测试基线。生产 SQL Composition Root 与完整 OAuth/Identity 运行集成仍在实施，不能描述为生产完成。

## 包边界

```text
src/health_platform/
├── domain/       业务领域边界
├── application/  应用用例边界
├── ports/        外部能力端口
├── adapters/     基础设施适配器
└── interfaces/   服务接口边界
```

这些目录只表达依赖方向，不预先固化业务 Schema。后续实现必须先有对应的 `READY` Slice。

## 验证

```bash
uv run uvicorn health_platform.platform.web.app:app --app-dir health_platform/src
uv run pytest health_platform/tests -v
uv run ruff check .
uv run mypy health_platform/src
```
