# 模块

`identity` 与 `audit` 在本 Slice 实现；`conversation`、`fact`、`goal`、`plan`、`risk`、`file`、`secret`、`agent_integration` 仅建立 `SKELETON`。

每个业务模块拥有 domain/application/ports/adapters/interfaces。模块不得调用其他模块 Repository；同步协作使用 Application Port，同事务变化使用进程内 Domain Event，可靠异步使用 Outbox。`platform` 只含跨模块技术能力，禁止无边界 `common/utils/helpers/services`。
