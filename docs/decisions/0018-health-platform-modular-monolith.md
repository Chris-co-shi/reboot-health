# 0018 Health Platform Python 模块化单体

## 状态

已确认，2026-07-12 生效。

## Context

Health Platform 需要在保持业务权威一致性的同时支持身份、审计、通知及后续健康模块。过早拆分微服务会放大事务、部署和合同成本。

## Decision

Health Platform 采用 Python 3.12、FastAPI 的模块化单体和单一部署单元。代码按业务模块纵向组织；`platform/` 仅承载数据库、配置、安全、加密、后台处理、Web 与可观测性等跨模块技术能力。每个 Pod 运行 FastAPI 和一个由 lifespan 管理、可停止、可观测的后台线程。

## Alternatives

- 独立微服务：当前规模下分布式事务和运维成本过高。
- Celery/独立 Worker：增加部署单元，不符合本 Slice 已确认边界。
- 单层 CRUD：无法保护领域不变量与模块边界。

## Consequences

同进程模块可通过 Application Port 和 Domain Event 协作；可靠远程副作用统一通过 PostgreSQL Outbox。模块仍需保持模型与依赖隔离，避免演变为大泥球。

## Security impact

身份、授权与审计可在一个事务边界内强制执行；Composition Root 是 Secret 与基础设施依赖的唯一组装点。

## Migration impact

不迁移 Java 代码。后续拆分服务时以模块 Port、Schema 和 Integration Event 为迁移边界。

## Superseded relationship

不恢复 ADR 0002 的全系统单体；本 ADR 仅细化 ADR 0012 中独立 Health Platform 服务的内部结构。

## Validation

依赖边界检查、FastAPI 启动/API 测试、后台线程生命周期测试、Ruff 与 Mypy。
