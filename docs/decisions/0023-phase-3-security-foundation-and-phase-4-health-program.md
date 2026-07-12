# 0023 Phase 3 安全底座与 Phase 4 综合健康闭环

## 状态

已确认，2026-07-12 生效。

## 背景

2026-07-12 架构冻结后的阶段路线把 Health Platform 业务权威、Fact、Goal、Plan、Risk、文件、RAG、Sandbox 和生产验收继续拆在 Phase 3C–3J 中。

后续产品讨论进一步明确：

1. Phase 3 应先完整交付生产技术底座、Identity、用户归属授权、服务主体授权和安全验收。
2. 训练、恢复、饮食、执行反馈和动态调整属于一个不可被技术阶段拆散的产品闭环。
3. 首个产品验证入口应采用独立 Web 用户端，以降低微信开放平台、审核和移动端调试对业务验证的阻塞。
4. 既有 `frontend/` 已被定义为 Vue 3 管理端，不能同时承担普通用户健康业务。

如果继续沿用旧阶段编号，Phase 3 会同时承担 Identity、Runtime 生产化、权限、安全以及全部健康业务，阶段完成条件过大且产品语义不清晰。

## 决策

### 1. Phase 3 边界

Phase 3 统一负责：

- Health Platform 生产基础与 PostgreSQL 持久化。
- Identity、OAuth/OIDC、Session、MFA 和账号生命周期。
- `USER`、`ADMIN_OPERATOR` 与服务主体权限。
- 所有业务对象的 `userId` 归属授权框架。
- Health Platform 与 health-agent 的 mTLS、短期 JWT 和 Tool Scope。
- health-agent 的生产 Task/Run/API/Worker、lease、fence、checkpoint、队列和恢复。
- 跨用户、跨任务、重放、Secret、日志脱敏和故障恢复验收。

Phase 3 不实现训练、恢复、饮食及其反馈调整业务。

### 2. Phase 4 边界

Phase 4 统一负责第一个完整健康产品闭环：

- Conversational Intake。
- Fact、Goal 和 Readiness。
- HealthProgram。
- TrainingPlan、RecoveryPlan、NutritionPlan。
- ProgramVersion 整体确认。
- Execution、Check-in 和 Feedback。
- AdjustmentCandidate。
- Risk 与 Reminder。
- 独立 Web 用户端端到端验收。

完整产品基线见 `docs/PHASE_4_BASELINE.md`。

### 3. 综合计划模型

采用 `HealthProgram` 统筹三个独立版本化子计划：

```text
HealthProgram
└── ProgramVersion
    ├── TrainingPlanVersion
    ├── RecoveryPlanVersion
    └── NutritionPlanVersion
```

用户分领域查看，但最终整体确认 `ProgramVersion`。Agent 只能生成候选，不能确认或发布。

### 4. 客户端顺序

- `clients/web/`：Phase 4 首个普通用户验证客户端。
- `frontend/`：继续作为 Vue 3 管理、运维、诊断和审计端。
- `clients/miniapp/`：Web 闭环稳定后的用户客户端。
- `clients/flutter/`：Web 闭环稳定后的用户客户端。

这只调整首发验证顺序，不改变所有正式客户端只能访问 Health Platform 的架构边界。

### 5. 实施治理

- 本 ADR 和 `PHASE_4_BASELINE.md` 先完成治理重基线。
- Phase 4 仍为 `DISCOVERY`，不得因为基线文档存在就开始业务实现。
- 每个 Phase 4 Slice 必须单独获得 `READY`，并具备 implementation specification、Allowed Paths、合同、迁移和验收。
- 医学阈值与营养数据源必须经过 Review/Spike，不允许实现 Agent 自行决定。

## 被替代的阶段语义

本 ADR 替代 `PHASE_STATUS.md` 中旧的 Phase 3D–3J 健康业务阶段编号语义。

旧阶段中的能力不会被删除，而是重新归类：

- 生产 Task/Run/API/Worker、授权、安全和故障恢复保留在 Phase 3。
- Fact、Goal、Plan、Risk、执行反馈和用户业务闭环迁移到 Phase 4。
- 文件、RAG、Sub-Agent、Sandbox、Kubernetes 等能力根据后续依赖重新排入 Phase 3 技术底座或 Phase 4 之后的增强阶段，不因本 ADR 自动进入实施。

## 迁移影响

- 更新根 README、文档首页、产品需求和阶段状态。
- 新增 `docs/PHASE_4_BASELINE.md`。
- 规划独立 `clients/web/`，本次只修改文档，不创建代码目录。
- 现有 Phase 3B Slice 2 实现与证据不变。
- 已完成 Phase 1–2C Runtime 不重写。
- 旧 Git 历史与实现规范继续可追溯，但不得作为当前阶段编号的依据。

## 后果

正面影响：

- Phase 3 有明确、可验收的安全和生产技术完成条件。
- Phase 4 围绕用户价值组织，不再把训练、恢复、饮食和反馈拆散到技术阶段。
- Web 可以快速验证端到端闭环，同时保持小程序与 Flutter 的未来协议兼容。
- 管理端和用户端职责清晰。

代价：

- 需要更新已有冻结文档和阶段编号引用。
- 旧 Issue、提示词和实施规范中的 Phase 3D–3J 名称需要人工识别并迁移。
- Phase 4 的 API、状态机和数据库合同仍需后续逐 Slice 设计。

## 非目标

本 ADR 不决定：

- 具体 Web 技术栈。
- 具体食物数据库或许可证。
- 医学风险阈值。
- 训练动作库和内容审核方案。
- 通知供应商。
- Phase 4 数据库表、索引和 API 字段。