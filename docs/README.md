<div align="center">

# Documentation Hub

### Product, architecture, domain and delivery truth for reboot-health

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
| [`architecture.md`](architecture.md) | Harness、Domain Kernel、调用和信任边界 |
| [`domain-model.md`](domain-model.md) | 业务聚合、语义和不变量 |
| [`api-db.md`](api-db.md) | 已实现 API、数据库、迁移与错误码 |
| [`safety-rules.md`](safety-rules.md) | 健康与系统安全规则 |
| [`mvp-exec-plan.md`](mvp-exec-plan.md) | 当前阶段、交付状态、验收和阻塞 |
| [`decisions/`](decisions/) | 已确认的 Architecture Decision Records |
| [`AGENTS.md`](AGENTS.md) | 文档治理和 README 视觉规范 |

## 🧭 Reading paths

### 了解项目

```text
README.md
→ product-scope.md
→ architecture.md
→ mvp-exec-plan.md
```

### 开始实现

```text
architecture.md
→ domain-model.md
→ api-db.md
→ safety-rules.md
→ 对应目录 AGENTS.md
```

### 审核架构决策

```text
decisions/README.md
→ 对应 ADR
→ architecture.md
```

## 🚦 Status language

| Status | Meaning |
|---|---|
| `DONE` | 自动化验证和要求的人工验收均完成 |
| `IMPLEMENTED_WITH_BLOCKERS` | 主体已实现，但仍有环境或验收阻塞 |
| `IN_PROGRESS` | 正在实施 |
| `TODO` | 尚未开始 |
| `OPEN` | 用户尚未确认 |
| `NEEDS_TECHNICAL_SPIKE` | 技术可行性待验证 |
| `NEEDS_MEDICAL_REVIEW` | 医学规则缺少专业依据 |

返回[项目首页](../README.md)。
