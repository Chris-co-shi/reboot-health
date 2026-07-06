<div align="center">

# Java Health Domain Kernel

### Trusted facts, deterministic safety and controlled domain tools

<p>
  <img alt="Java 21" src="https://img.shields.io/badge/Java-21-ED8B00?logo=openjdk&logoColor=white">
  <img alt="Spring Boot" src="https://img.shields.io/badge/Spring%20Boot-3.x-6DB33F?logo=springboot&logoColor=white">
  <img alt="PostgreSQL 17" src="https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white">
  <img alt="Role" src="https://img.shields.io/badge/Role-Trusted%20Domain%20Kernel-6C5CE7">
</p>

**Java 决定什么允许做，并负责把已确认事实可靠保存。**

</div>

## 🎯 Responsibilities

Java Health Domain Kernel 负责：

- 已确认用户事实、目标、健康约束和计划状态。
- 确定性安全规则与领域不变量。
- 设备身份、认证和权限边界。
- 审计、幂等、revision 和事务一致性。
- AgentRun 权威状态与 Python Runtime 调用边界。
- 面向业务意图的 Agent Tool Contract。

它不负责 Skill 选择、Prompt 编排、模型控制流或 Flutter 展示策略。

## 🧩 Modules

| Module | Responsibility |
|---|---|
| `profile` | 用户档案与已确认健康约束 |
| `goal` | 目标唯一事实来源 |
| `plan` | Plan 与 7 天 PlanVersion 发布引擎 |
| `agent` | AgentRun 状态、Runtime 适配与结果校验 |
| `device` | bootstrap、配对、认证、凭据与设备管理 |
| `audit` | 追加写业务与安全审计 |
| `idempotency` | 写请求幂等与敏感结果安全重放 |

## 🧱 Dependency direction

```text
Controller
    ↓
Application Service
    ↓
Domain
    ↓
Repository Port
    ↑
Persistence Adapter
```

关键边界：

- 数据库事务中不调用 Python 或其他远程服务。
- Python 只能通过受控 Tool Contract 使用领域能力。
- 已确认计划继续由现有 PlanVersion 引擎发布。
- 业务模块不直接依赖其他模块的 Mapper。

## ✅ Verify

```bash
cd backend
mvn test
```

涉及数据库迁移、锁、认证、状态机、Tool、审计或幂等时，必须提供对应自动化测试。

## 📚 References

- [Backend rules](AGENTS.md)
- [System architecture](../docs/architecture.md)
- [Domain model](../docs/domain-model.md)
- [API and database](../docs/api-db.md)
- [Safety rules](../docs/safety-rules.md)
