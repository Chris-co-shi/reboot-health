# 阶段状态（FROZEN ROADMAP）

## 1. 状态定义

| 状态 | 含义 |
|---|---|
| `DONE` | 实现、自动化验证和要求的真实验收均完成 |
| `DONE_EXPLICIT` | 能力完成但需显式启用，尚非默认生产流程 |
| `FROZEN` | 产品或架构合同已经人工确认，代码不得反向修改 |
| `DISCOVERY` | 正在讨论和建立产品/架构基线，不允许实施业务代码 |
| `READY` | Phase/Slice 范围、合同、路径和验收已批准，可以实现 |
| `IN_PROGRESS` | 正在实施 |
| `IMPLEMENTED_WITH_BLOCKERS` | 主体已实现，但仍缺少关键真实验收或生产门槛 |
| `TODO` | 已在路线中定义，但尚未批准进入实施 |
| `BLOCKED` | 必须先完成依赖、ADR 或技术 Spike |
| `NEEDS_TECHNICAL_SPIKE` | 实现技术需要验证，但不得改变冻结边界 |
| `NEEDS_MEDICAL_REVIEW` | 医学阈值或规则缺少专业审核 |

代码存在、Mock 通过、静态检查通过或文档写完均不能单独标记 `DONE`。

## 2. 当前总状态

```text
Phase 1 / 1.1 / 1.2 / 1.3：DONE
Phase 2A：DONE
Phase 2B：DONE_EXPLICIT
Phase 2C：DONE
Phase 3A Architecture Freeze：FROZEN

Phase 3：IN_PROGRESS
- Phase 3B Repository and Platform Foundation：IN_PROGRESS
- 当前活动 Slice：Phase 3B Slice 2 Health Platform Production Foundation and Identity

Phase 4 Integrated Health Program Loop：DISCOVERY
- 产品与阶段重基线已形成
- 所有业务 Slice 均未 READY
```

## 3. 阶段边界重基线

ADR 0023 自 2026-07-12 起替代旧 Phase 3C–3J 路线中的健康业务阶段语义。

### Phase 3 当前边界

Phase 3 负责：

- Health Platform 生产基础与 PostgreSQL 持久化。
- Identity、OAuth/OIDC、Session、MFA 和账号生命周期。
- 用户对象归属授权和最小 RBAC。
- Health Platform 与 health-agent 的 mTLS、短期 JWT 和 Tool Scope。
- health-agent 生产 Task/Run/API/Worker、lease、fence、checkpoint、队列和恢复。
- Secret、日志脱敏、跨用户、跨任务、重放和故障恢复验收。

Phase 3 不负责训练、恢复、饮食及其执行反馈业务。

### Phase 4 当前边界

Phase 4 负责：

- Conversational Intake。
- Fact、Goal 和 Readiness。
- HealthProgram。
- TrainingPlan、RecoveryPlan、NutritionPlan。
- Execution、Check-in 和 Feedback。
- AdjustmentCandidate。
- Risk 和 Reminder。
- 独立 Web 用户端端到端闭环。

详细产品基线见 [`PHASE_4_BASELINE.md`](PHASE_4_BASELINE.md)。

## 4. 已完成实现事实

### Phase 1：Provider 与通用模型合同

状态：`DONE`

已完成：

- Python 当前主目录为 `health_agent/`。
- OpenAI-compatible Provider 使用真实模型配置。
- 通用 `complete_turn(...)`、普通文本、Tool Call、usage 和 finish reason。
- 产品 Bootstrap 不回退测试替身。
- `INITIAL_PLANNING` 仅为显式 legacy compatibility。

### Phase 2A：通用只读 Tool Call Agent Loop

状态：`DONE`

已完成：

- system/user/assistant/tool 消息合同。
- assistant `tool_calls` 与 `tool_call_id`。
- ToolRegistry 白名单、ToolExecutor、参数校验和结构化错误。
- 最大模型回合、最大 Tool 次数和整体超时。
- `convert_weight_unit` 正式只读工具。
- 真实链路：模型 → Tool Call → Tool Result → 模型。

历史验收摘要：

```text
确定性测试：145 个通过，默认跳过 2 个显式真实集成测试
真实模型调用轮数：2
真实工具调用次数：1
真实转换：190 jin → 95 kg
未经过 INITIAL_PLANNING
```

### Phase 2B：Runtime 状态、确认、恢复和 JSON 安全基础

状态：`DONE_EXPLICIT`

已完成：

- AgentSession、PendingAction 和 ConfirmationCoordinator。
- JSON Session/PendingAction Store。
- CAS、跨进程锁、原子替换和安全文件键。
- RUNNING lease、heartbeat 和 fencing。
- execution checkpoint。
- stale recovery；仅 `DRIVE_READY` 自动恢复。
- orphan PendingAction 扫描和清理。

限制：

- JSON Store 是本地明文，不是生产持久化。
- 默认 one-shot 入口仍使用内存 Store。
- 正式 PostgreSQL、API/Worker、Redis 调度和生产 Confirmation 尚未实现。

### Phase 2C：Interactive Session & Conversation Context

状态：`DONE`

已完成：

- `scripts/agent_chat.py`。
- 同进程复用 Runtime Components。
- 同一 `session_id` 连续消息。
- memory/json 显式 Store。
- `/help`、`/new`、`/status`、`/resume`、`/exit`。
- JSON 跨进程恢复。
- 普通 Clarification 不创建 PendingAction。

历史验收摘要：

```text
确定性测试：375 个通过，默认跳过 2 个显式真实集成测试
真实同进程连续对话：2 次 Agent Run
真实 JSON 跨进程恢复：2 次 Agent Run
真实模型回合：1 + 1 / 1 + 1
Tool Call：0
未经过 INITIAL_PLANNING
```

## 5. Phase 3A：Architecture Freeze

状态：`FROZEN`

冻结日期：2026-07-12

核心结论：

- Health Platform 与 health-agent 独立服务。
- 所有客户端只访问 Health Platform。
- 持久异步 Task/Run、HTTP + SSE。
- PostgreSQL 权威 + Redis Streams 调度。
- Outbox/Inbox/Callback/Pull 对账。
- Platform Tool API 是业务数据唯一访问路径。
- Fact/Plan/Risk/File 保持用户确认和版本语义。
- Context 压缩、pgvector RAG、顺序一层 Sub-Agent。
- Sandbox、Secret、MinIO 和彻底删除。
- 目标部署为六 VM Kubernetes。
- 五类生产验收全部通过后才可生产使用。

2026-07-12 ADR 0023 进一步重划 Phase 3/4 实施边界，但不推翻上述双服务、数据权威、安全和可恢复架构。

## 6. Phase 3 实施路线

### Phase 3B：Repository and Platform Foundation

状态：`IN_PROGRESS`

#### Slice 1：Repository Restructure and Legacy Removal

状态：`DONE`

实施规范：[`implementation/phase-3b-slice-1-repository-restructure.md`](implementation/phase-3b-slice-1-repository-restructure.md)

完成事实：

- 旧 Java 后端、Maven/Flyway、设备认证和旧 AgentRun 权威已删除。
- Python Health Platform 框架无关骨架已建立。
- health-agent Phase 1–2C 代码与测试完整保留。
- Flutter、Vue、Mini Program、合同与 Kubernetes 目标目录已建立或重新定位。
- Vue 保持管理端定位。
- 未执行真实业务闭环、Kubernetes、数据库、Redis、MinIO 或端到端验收。

#### Slice 2：Health Platform Production Foundation and Identity

状态：`IN_PROGRESS`

Primary Module：`health_platform`。

实施规范：[`implementation/phase-3b-slice-2-health-platform-production-foundation.md`](implementation/phase-3b-slice-2-health-platform-production-foundation.md)

目标：

- 模块化单体生产基础。
- Identity 第一版。
- Audit/Outbox。
- 缓存降级。
- 加密和邮件。
- 可观测性和 Probe。
- SQLAlchemy UoW 与 PostgreSQL 生产装配。

当前有效证据：

- Port 抽象、InMemory UoW 与 IdentityService 已重构。
- HTTP 接口通过 UoW，不再直接读取内部状态。
- Ruff 通过。
- Mypy 对 34 个源文件 0 错误。
- 30 项非 PostgreSQL 测试通过，4 项 PostgreSQL 测试按环境条件未完成。
- Bandit 未发现中高风险问题。
- pip-audit 未发现已知漏洞。
- health-agent 376 项回归通过，2 项显式真实 LLM 测试按设计跳过。

未完成：

- SQL Repository 和双向 ORM mapper。
- SQLAlchemy UoW 与生产 Composition Root。
- Alembic 审计链和 OAuth 幂等迁移。
- 缺数据库或密钥时的生产启动门禁。
- 完整 OAuth/Client Credentials 闭环。
- 邮件 Outbox Processor。
- OTel 与数据库 readiness。
- Refresh 并发轮换、RLS 上下文清理、Redis 降级和审计链真实 PostgreSQL 验收。
- 完整权限用例和安全验收。

Slice 2 与 Phase 3B 不得标记为 `DONE`，也不得描述为 Identity 已完整生产化。

### Phase 3C：Ownership Authorization and Service Trust

状态：`TODO`

进入 `READY` 前必须建立 implementation specification。

目标：

- 所有未来业务对象统一 `userId` 归属授权机制。
- `USER` 与 `ADMIN_OPERATOR` 的最小 RBAC。
- `SERVICE_HEALTH_AGENT` 独立服务主体。
- Platform → Agent Task 短期凭证。
- Agent → Platform Tool Scope 凭证。
- mTLS、audience、jti、expiry、revocation 和重放防护。
- 跨用户、跨任务、跨 Run、跨 Tool Scope fail-closed 测试。

本阶段只建立通用授权框架，不实现健康业务对象。

### Phase 3D：Production Agent Runtime and Integration

状态：`TODO`

目标：

- PostgreSQL Task/Run/Step/Checkpoint/ToolCall/Outbox。
- `health-agent-api` 和 `health-agent-worker`。
- lease/fence/checkpoint 从 JSON 迁移到生产存储。
- Redis Streams Queue Port 和 PostgreSQL reconciler。
- Platform 与 Agent 的 Task、Callback、Pull 和 SSE 最小闭环。
- 可恢复 WAITING_USER_INPUT 和 PendingAction 基础。

不得把本地 CLI/JSON Store 作为 Phase 4 的生产依赖。

### Phase 3E：Security, Recovery and Foundation Acceptance

状态：`TODO`

目标：

- Identity、权限、服务凭证和 Tool Scope 端到端验收。
- API、Worker、PostgreSQL、Redis 故障恢复。
- Outbox/Inbox 幂等和乱序测试。
- Secret、日志脱敏、Token 重放、SSRF 和跨用户测试。
- 管理员技术性干预与审计。
- 备份、恢复和最小运维门槛。

Phase 3E 完成后，才能评估 Phase 4 首个业务 Slice 是否可进入 `READY`。

## 7. Phase 4：Integrated Health Program Loop

状态：`DISCOVERY`

产品基线：[`PHASE_4_BASELINE.md`](PHASE_4_BASELINE.md)

### 4A：Governance Re-baseline

状态：`IN_REVIEW`

目标：

- ADR 0023。
- Phase 3/4 边界重划。
- Web 用户端与 Vue Admin 分离。
- Phase 4 产品决策基线。
- 更新 README、产品需求、阶段状态和 ADR 索引。

本 Slice 只修改文档。合并并完成一致性复核后才能标记为 `DONE`。

### 4B：Conversational Intake, Fact, Goal and Readiness

状态：`DISCOVERY`

- 纯对话采集。
- FactCandidate / GoalCandidate。
- 分级确认。
- ReadinessPolicy。
- 缺失、冲突和风险追问。

### 4C：HealthProgram Core

状态：`DISCOVERY`

- HealthProgram。
- ProgramCycle / ProgramPhase。
- ProgramVersion。
- 三个独立子计划版本引用。
- Fact/Goal/Risk Snapshot。
- 候选、确认、替代、拒绝和失效。

### 4D：Training Planning

状态：`DISCOVERY`

- 训练周期、阶段、周计划和每日训练。
- 动作、组次、次数、负荷、RPE 和替换边界。
- 进阶、维持、降载和暂停规则。

### 4E：Recovery Planning

状态：`DISCOVERY`

- 睡眠、主动恢复、灵活性和恢复任务。
- 疲劳、酸痛、压力和 Readiness。
- 与训练计划的跨域一致性。

### 4F：Nutrition Planning

状态：`DISCOVERY`

- 热量和宏量营养目标。
- MealSchedule、FoodReference 和替换。
- 数据来源和 AI 估算不确定性。
- 营养数据库和许可证 Spike。

### 4G：Program Generation, Review and Confirmation

状态：`DISCOVERY`

- 完整周期框架。
- 近期滚动详细计划。
- 分领域查看。
- 最终整体确认 ProgramVersion。

### 4H：Execution, Check-in and Feedback

状态：`DISCOVERY`

- 默认轻量执行记录。
- 可选详细训练和饮食记录。
- 事件反馈、每日 Check-in 和周期复盘。
- 历史纠错和不可静默覆盖。

### 4I：Adjustment, Risk and Reminder

状态：`DISCOVERY`

- 多来源调整触发。
- AdjustmentCandidate。
- R0–R4 确定性风险等级。
- ReminderTask、免打扰、延后、过期、幂等和降频。

### 4J：Web End-to-End Acceptance

状态：`DISCOVERY`

- 独立 `clients/web/` 普通用户端。
- 自然对话到新 ProgramVersion 的完整旅程。
- 领域不变量、安全、恢复和提醒验收。

## 8. 后续增强能力

以下能力仍然有效，但具体阶段编号需在 Phase 4 依赖明确后重新安排：

- File、MinIO、上传扫描和彻底删除。
- PDF/图片 Sandbox 解析和逐项确认。
- Context、pgvector RAG、reranker fallback。
- 一层顺序 Sub-Agent。
- Provider fallback 和模型预算。
- Sandbox、Secret 和高级安全加固。
- Kubernetes、可观测性、高可用、灰度和容量告警。

这些能力不得因为旧 Phase 3F–3I 名称存在于历史提交、Issue 或提示词中而自行开始实现。

## 9. 已知风险与阻塞

| 风险 | 当前决定 |
|---|---|
| 单 Hyper-V 宿主机 | 接受；不能声明跨主机 HA |
| 单物理 SSD | 接受；保留容量余量并持续告警 |
| 无 NAS/云外部备份 | 接受先建设；生产使用前必须重新评估 |
| 医学阈值未专业审核 | `NEEDS_MEDICAL_REVIEW`，不得自行实现 |
| 营养数据库与许可证未确定 | `NEEDS_TECHNICAL_SPIKE`，不得由实现 Agent 随意选择 |
| 当前 Runtime 是 CLI/JSON | 仅 Phase 1–2C 实现事实，不等于生产服务 |
| Health Platform InMemory UoW | 仅用于 local/test 显式路径；production 已使用 PostgreSQL SQLAlchemy UoW |
| Web 用户客户端尚不存在 | 仅文档规划，Phase 4 Slice 未 READY |

## 10. 进入实施的强制条件

每个 Slice 必须先在 `implementation/` 增加规范，至少包含：

```text
Phase / Slice
Primary Module
Goal
Authoritative Documents
Allowed Paths
Forbidden Paths
Contract Changes
Migration / Compatibility
Required Verification
Definition of Done
Out of Scope
```

用户确认并将 Slice 标记 `READY` 后，Codex 或人工开发才能修改代码。

Phase 4 的 Discovery 文档、ADR、讨论记录或候选领域模型不能替代 implementation specification。

## 11. 提示词约束

交给 Codex、Claude Code、Hermes、Trae 或其他实现 Agent 的提示词必须：

- 引用当前 `PHASE_STATUS.md`、相关 ADR 和权威文档。
- 明确 Phase/Slice 与状态。
- 不得继续使用被 ADR 0023 替代的 Phase 3D–3J 健康业务编号。
- 不得自行决定医学阈值、食物数据库、Web 技术栈或未冻结合同。
- 发现冲突时停止实施并报告。
- 不得把骨架、Mock、内存实现或文档存在描述成生产能力已完成。

## 12. Phase 3B Slice 2 — Identity SQL Persistence（2026-07-12）

- 当前全部 Identity Repository Port 已完成显式 Domain/Row 双向 Mapper 和 SQL Repository；Application 层未引入 SQLAlchemy。
- 新增 `SqlAlchemyIdentityUnitOfWork`：每实例独立 Session/事务，显式 commit，异常/未提交 rollback，成功提交后才运行 hooks，最终关闭 Session。
- production Composition Root 装配 Engine、SessionFactory、SQL UoW、SQL Audit/Outbox、Redis Cache（配置启用时）、Encryption、Email Port 和 IdentityService；不再回退 InMemory。
- 新增 0003 migration：AuthorizationGrant、DeletionRequest、完整 FORCE RLS/Policy；Head 为 `20260712_0003`，未修改 0001/0002。
- readiness 验证 PostgreSQL、代码单 Head 与 DB current revision；不执行 migration/create_all，错误响应仅返回稳定分类。
- 测试基础设施优先 `TEST_DATABASE_URL`（数据库名必须包含 test），否则使用本地禁用 Ryuk 的一次性 PostgreSQL 17 容器并自动清理。
- 真实 PostgreSQL 17.10：**13 passed, 0 failed, 0 skipped, 0 error**；覆盖重启持久化、整体回滚、10 路 Audit 单链、真实行锁、RLS/连接复用、OAuth 幂等和生产 readiness。
- 非 PG：**40 passed, 13 deselected**；全量：**53 passed**；coverage **91.03%**。
- 本轮 SQL Foundation 完成，但管理员用例、完整 Refresh 并发/重放、MFA disable/reset、安全问题、Client Credentials、完整限流、SMTP Processor 与 OTel 仍未完成；Phase 3B Slice 2 保持 `IN_PROGRESS`。
