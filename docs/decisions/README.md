<div align="center">

# Architecture Decision Records

### Approved and superseded decisions for reboot-health

![ADR](https://img.shields.io/badge/Format-ADR-6C5CE7)
![Architecture](https://img.shields.io/badge/Architecture-FROZEN-00B894)

</div>

> ADR 记录重大决策及其演进。当前有效产品和工程规则仍必须同步体现在 `docs/` 权威文档中。历史 ADR 不能覆盖 2026-07-12 冻结文档。

## Decision index

| ID | Decision | Status | Current meaning |
|---|---|---|---|
| [0001](0001-personal-single-user-scope.md) | 单人个人使用范围 | 已扩展 | 第一阶段单用户，但所有数据保留 userId 隔离和未来多用户边界 |
| [0002](0002-modular-monolith.md) | 模块化单体架构 | 已替代 | 由 0012 的 Health Platform + health-agent 双服务替代 |
| [0003](0003-ai-proposal-only.md) | AI 候选与确认边界 | 已扩展 | 由 0014 细化 Fact、Plan、Risk 与人工决定权 |
| [0004](0004-windows-docker-postgresql.md) | Docker 与 PostgreSQL 17 | 已替代 | 由 0017 的六 VM Kubernetes 正式拓扑替代 |
| [0005](0005-frontend-pnpm.md) | 前端使用 pnpm | 历史实现约束 | 仅适用于对应 Vue 工程，不决定系统架构 |
| [0006](0006-redis-not-in-mvp.md) | Redis 暂不进入 MVP | 已替代 | 由 0013 的 Redis Streams 调度和 PostgreSQL 权威替代 |
| [0007](0007-plan-version-idempotency.md) | 计划版本和 POST 幂等 | 已扩展 | 关键语义保留，并由 0014/API 合同扩展 |
| [0008](0008-m25a-flutter-agent-device-bootstrap.md) | Flutter、Runtime 与设备初始化 | 历史 | 旧多运行时技术骨架；Flutter 目标客户端以冻结文档为准 |
| [0009](0009-ai-first-product-and-module-boundaries.md) | Java 领域内核与 Python Agent | 已替代 | 先由 0010 替代，现最终由 0012 替代 |
| [0010](0010-python-modular-monolith-and-agent-loop.md) | Python 模块化单体与通用 Agent Loop | 部分保留/架构已替代 | Agent Loop 语义保留；单体目标由 0012、0013、0017 替代 |
| [0011](0011-session-context-memory-boundaries.md) | Session、Context、Memory 与领域事实边界 | 已扩展 | 基础分层保留，由 0015 和冻结文档扩展 |
| [0012](0012-health-platform-and-agent-service-split.md) | Health Platform 与 health-agent 服务拆分 | 已确认 | 业务权威与通用执行层独立部署 |
| [0013](0013-durable-agent-execution-and-event-sync.md) | 持久异步执行、调度与事件同步 | 已确认 | PostgreSQL 权威、Redis Streams、Outbox/Inbox 和对账 |
| [0014](0014-facts-plans-risks-and-human-authority.md) | Fact、Plan、风险与人工决定权 | 已确认 | 候选、逐项确认、Plan 发布、历史纠正和风险二次确认 |
| [0015](0015-context-rag-and-subagent-boundaries.md) | Context、RAG 与 Sub-Agent | 已确认 | 结构化 Summary、pgvector 和一层顺序委派 |
| [0016](0016-sandbox-secrets-and-file-lifecycle.md) | Sandbox、Secret 与文件生命周期 | 已确认 | 不可信执行隔离、Platform Secret 中心、MinIO 和彻底删除 |
| [0017](0017-kubernetes-six-vm-and-architecture-freeze.md) | 六 VM Kubernetes 与架构冻结 | 已确认 | 全组件 K8s、灰度、单宿主机风险和 docs-first 治理 |
| [0018](0018-health-platform-modular-monolith.md) | Health Platform Python 模块化单体 | 已确认 | 独立 Platform 服务内部采用 FastAPI 模块化单体与 lifespan 后台线程 |
| [0019](0019-health-platform-persistence-and-transactions.md) | Health Platform 持久化与事务 | 已确认 | SQLAlchemy/psycopg、模块 Schema、Alembic、UoW、RLS 与 Outbox |
| [0020](0020-identity-oauth-oidc-and-session-security.md) | Identity、OAuth/OIDC 与 Session 安全 | 已确认 | 不透明用户 Token、PKCE、RS256、MFA、设备会话与恢复闭环 |
| [0021](0021-health-platform-cache-background-and-observability.md) | 缓存、后台处理与可观测性 | 已确认 | PostgreSQL 权威、Redis 降级、Outbox 线程、OTel 与 Probe |

## Status rules

- `已确认`：当前有效，且已同步到权威文档。
- `已扩展`：核心方向仍有效，但后续 ADR/权威文档提供完整规则。
- `部分保留/架构已替代`：历史实现语义继续复用，但目标部署或职责划分已经改变。
- `已替代`：不再作为当前实现依据，只用于理解历史。
- `历史`：记录旧阶段事实，不进入当前阅读路径。

## Change rule

新增或替代 ADR 时必须：

1. 更新本索引。
2. 更新所有受影响的权威文档。
3. 更新 `PHASE_STATUS.md` 的影响和实施阶段。
4. 经过用户人工批准。
5. 批准前不得修改代码或生成实施提示词。

返回[文档首页](../README.md)。
