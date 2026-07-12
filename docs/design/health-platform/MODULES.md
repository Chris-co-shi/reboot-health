# 模块

`identity` 与 `audit` 在本 Slice 实现；`conversation`、`fact`、`goal`、`plan`、`risk`、`file`、`secret`、`agent_integration` 仅建立 `SKELETON`。

每个业务模块拥有 domain/application/ports/adapters/interfaces。模块不得调用其他模块 Repository；同步协作使用 Application Port，同事务变化使用进程内 Domain Event，可靠异步使用 Outbox。`platform` 只含跨模块技术能力，禁止无边界 `common/utils/helpers/services`。

当前 Slice 进展：

- `identity` 的 HTTP 接口（DTO、路由、`principal` 依赖、IdentityError handler）已迁至 `modules/identity/interfaces/http.py`；`platform/web/app.py` 仅保留 Composition Root、Probe、lifespan 和 `include_router`。
- 顶层 `health_platform.{adapters,application,domain,interfaces,ports}` 空骨架已删除；SKELETON 模块的占位子包已删除并合并通用骨架规则至 `modules/AGENTS.md`。
- `identity` 与 `audit` 模块保留各自专属的 `domain / application / adapters / ports / interfaces` 五层结构。
