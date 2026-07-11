<div align="center">

# Documentation Hub

### Product, architecture, implementation and delivery truth for reboot-health

<p>
  <img alt="Docs" src="https://img.shields.io/badge/Docs-Single%20Source%20of%20Truth-6C5CE7">
  <img alt="Language" src="https://img.shields.io/badge/Language-Chinese-E17055">
</p>

</div>

> 本目录维护项目的权威文档。相同事实只允许在一个文档中完整描述，其他位置应链接到它。

## 📚 Document map

| 文档 | 唯一职责 |
|---|---|
| [`product-scope.md`](product-scope.md) | 产品定位、用户体验、范围与非目标 |
| [`architecture.md`](architecture.md) | Python 模块化单体、Agent Runtime、Provider、Tool、Session 与信任边界 |
| [`domain-model.md`](domain-model.md) | 业务聚合、语义和需要迁移的不变量 |
| [`api-db.md`](api-db.md) | 历史已实现 API/数据库合同与后续迁移参考 |
| [`safety-rules.md`](safety-rules.md) | 健康与系统安全规则及待审核边界 |
| [`mvp-exec-plan.md`](mvp-exec-plan.md) | 当前阶段、状态、范围、验收和阻塞 |
| [`implementation/`](implementation/README.md) | 已确认阶段的 IDE/人工开发交接规范 |
| [`decisions/`](decisions/README.md) | 已确认及已替代的 Architecture Decision Records |
| [`AGENTS.md`](AGENTS.md) | 文档治理和 README 规范 |

## 🧭 当前开发阅读路径

### 了解当前项目

```text
../README.md
→ product-scope.md
→ architecture.md
→ mvp-exec-plan.md
→ decisions/0010-python-modular-monolith-and-agent-loop.md
→ decisions/0011-session-context-memory-boundaries.md
```

### 开始当前 Phase 2C 实现

```text
../AGENTS.md
→ ../health_agent/AGENTS.md
→ architecture.md
→ mvp-exec-plan.md
→ decisions/0011-session-context-memory-boundaries.md
→ implementation/phase-2c-interactive-session-cli.md
→ ../health_agent/README.md
```

### 回顾已完成 Phase 2A

```text
implementation/phase-2a-read-only-tool-call-loop.md
```

该文档是历史验收参考，不再代表当前待实施阶段。

### 迁移历史业务语义

```text
architecture.md
→ domain-model.md
→ api-db.md
→ safety-rules.md
→ decisions/0007-plan-version-idempotency.md
```

历史 Java/Flutter 文档和代码只作为迁移参考，不是当前运行入口。

## 🚦 Status language

| Status | Meaning |
|---|---|
| `DONE` | 自动化验证和要求的真实运行验收均完成 |
| `DONE_EXPLICIT` | 自动化验收完成，但能力需要显式启用或调用，尚非默认产品流程 |
| `READY` | 设计、范围和验收标准已确认，可以开始实现 |
| `IN_PROGRESS` | 正在实施 |
| `IMPLEMENTED_WITH_BLOCKERS` | 主体存在，但仍有真实环境或关键验收阻塞 |
| `TODO` | 尚未开始 |
| `BLOCKED` | 被依赖或未确认事项阻塞 |
| `OPTIONAL` | 不影响核心产品闭环的可选能力 |
| `OPEN` | 用户尚未确认 |
| `NEEDS_TECHNICAL_SPIKE` | 技术可行性待验证 |
| `NEEDS_MEDICAL_REVIEW` | 医学规则缺少专业依据 |

返回[项目首页](../README.md)。
