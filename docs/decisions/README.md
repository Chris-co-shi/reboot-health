<div align="center">

# Architecture Decision Records

### Confirmed product and architecture decisions for reboot-health

<img alt="ADR" src="https://img.shields.io/badge/Format-ADR-6C5CE7">
<img alt="Status" src="https://img.shields.io/badge/Scope-Confirmed%20Decisions-00B894">

</div>

> 本目录只记录已经确认、需要长期保留的产品和架构决策。未确认事项应留在对应权威文档中，并标记为 `OPEN`、`NEEDS_TECHNICAL_SPIKE` 或 `NEEDS_MEDICAL_REVIEW`。

## Decision index

| ID | Decision | Status | Summary |
|---|---|---|---|
| [0001](0001-personal-single-user-scope.md) | 单人个人使用范围 | 已确认 | 私有单用户优先，但保留明确数据归属边界 |
| [0002](0002-modular-monolith.md) | 模块化单体架构 | 已扩展 | 保持单体部署和模块边界；当前 Python 实现方向见 0010 |
| [0003](0003-ai-proposal-only.md) | AI 候选与确认边界 | 已确认 | AI 生成候选；重要变化需确认；低风险调整可受控执行 |
| [0004](0004-windows-docker-postgresql.md) | Docker 与 PostgreSQL 17 | 历史待迁移 | 描述旧部署与数据库运行方式，不代表当前 Python Runtime 已接入 |
| [0005](0005-frontend-pnpm.md) | 前端使用 pnpm | 历史 | Vue 内部调试工具的包管理方式 |
| [0006](0006-redis-not-in-mvp.md) | Redis 暂不进入 MVP | 已确认 | 当前阶段避免引入非必要基础设施 |
| [0007](0007-plan-version-idempotency.md) | 计划版本和 POST 幂等 | 语义保留待迁移 | 后续 Python 实现仍需保留版本、revision 与幂等语义 |
| [0008](0008-m25a-flutter-agent-device-bootstrap.md) | Flutter、Runtime 与设备初始化 | 历史 | 旧多运行时技术骨架，不作为当前实施入口 |
| [0009](0009-ai-first-product-and-module-boundaries.md) | Health Agent Harness 与 Java 领域内核 | 已替代 | 旧 Python/Java/Flutter 职责划分，由 0010 替代 |
| [0010](0010-python-modular-monolith-and-agent-loop.md) | Python 模块化单体与通用 Agent Loop | 已确认 | Python 是当前与目标 Runtime；按有限轮次 Tool Call Loop 和纵向切片演进 |
| [0011](0011-session-context-memory-boundaries.md) | Session、Context、Memory 与领域事实边界 | 已确认 | 连续对话、上下文摘要、领域事实和 Memory Candidate 分层管理 |

## Status rules

- `已确认`：当前有效决策。
- `已扩展`：仍有效，但由后续 ADR 补充。
- `已替代`：保留历史，正文必须链接替代它的 ADR。
- `历史`：只描述旧阶段事实，不作为当前实施依据。
- `语义保留待迁移`：旧实现不再扩展，但关键业务语义必须在后续 Python 迁移中保留。

不要删除历史 ADR，也不要把路线设想、实现笔记或临时 TODO 写成架构决策。

返回[项目 README](../../README.md)或查看[架构方案](../architecture.md)。
