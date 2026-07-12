# 阶段状态（FROZEN）

## 1. 状态定义

| 状态 | 含义 |
|---|---|
| `DONE` | 实现、自动化验证和要求的真实验收均完成 |
| `DONE_EXPLICIT` | 能力完成但需显式启用，尚非默认生产流程 |
| `FROZEN` | 产品和架构合同已经人工确认，代码不得反向修改 |
| `READY` | Phase/Slice 范围、合同、路径和验收已批准，可以实现 |
| `IN_PROGRESS` | 正在实施 |
| `IMPLEMENTED_WITH_BLOCKERS` | 主体已实现，但仍缺少关键真实验收或生产门槛 |
| `TODO` | 尚未批准进入实施 |
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

当前活动代码 Phase：Phase 3B
当前活动 Slice：无；Slice 1 已完成，下一 Slice 尚未批准
```

自 2026-07-12 起，旧的“Phase 3A 健康领域只读工具”路线废止，不得继续使用该名称实施代码。

## 3. 已完成实现事实

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

## 4. Phase 3A：Architecture Freeze

状态：`FROZEN`

冻结日期：2026-07-12

交付物：

- `docs/PRODUCT_REQUIREMENTS.md`
- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/DOMAIN_MODEL.md`
- `docs/STATE_MACHINES.md`
- `docs/API_CONTRACTS.md`
- `docs/SECURITY_AND_PRIVACY.md`
- `docs/DEPLOYMENT_AND_OPERATIONS.md`
- `docs/PHASE_STATUS.md`
- `docs/decisions/` 新 ADR 和替代关系
- 根目录和模块级 Agent 规则

Phase 3A 不修改业务代码、数据库 Schema 或部署清单。

冻结结论：

- Health Platform 与 health-agent 独立服务。
- 小程序、Flutter、Vue 只访问 Health Platform。
- 持久异步 Task/Run、HTTP + SSE。
- PostgreSQL 权威 + Redis Streams 调度。
- Outbox/Inbox/Callback/Pull 对账。
- Platform Tool API 是业务数据唯一访问路径。
- Fact/Plan/Risk/File 的用户确认和版本语义。
- Context 压缩、pgvector RAG、顺序一层 Sub-Agent。
- Sandbox、Secret、MinIO 和彻底删除。
- 6 VM Kubernetes，全组件运行在 K8s。
- 五类生产验收全部通过后才可生产使用。

## 5. 后续实施路线

以下是冻结后的 Phase 边界。每个 Phase 进入 `READY` 前必须进一步拆成可审查 Slice，并新增 implementation 规范。

### Phase 3B：仓库重组和服务骨架

状态：`IN_PROGRESS`

#### Slice 1：Repository Restructure and Legacy Removal

状态：`DONE`

Primary Module：仓库目录结构、Health Platform 骨架和 legacy 清理。

实施规范：[`implementation/phase-3b-slice-1-repository-restructure.md`](implementation/phase-3b-slice-1-repository-restructure.md)

完成记录：

- 旧 Java 后端、Maven/Flyway、设备认证和旧 AgentRun 权威已删除。
- Python Health Platform 框架无关骨架已建立；未实现业务、API 或数据库。
- health-agent Phase 1–2C 代码与测试完整保留，376 项确定性测试通过，2 项显式真实 LLM 测试按设计跳过；专项多进程、lease、恢复和 orphan 测试通过。
- Flutter 已成为只面向 Health Platform 的正式客户端空壳；`pub get`、`analyze` 和 1 项测试通过。
- Vue 已成为正式 Admin Shell；锁文件安装、类型检查和构建通过。
- 小程序、合同和 Kubernetes 目标目录已建立；旧 Compose 已删除。
- Health Platform 编译通过；当前骨架没有单元测试用例。
- 未执行真实 LLM、Kubernetes、数据库、Redis、MinIO 或端到端业务验收；均不属于本 Slice。
- 未越过 Allowed Paths；未修改 `health_agent/agent/**` 或 `health_agent/tests/**`。

目标：

- 明确 Health Platform 和 health-agent 的代码目录/仓库策略。
- 建立 Python 服务骨架、配置、合同包和测试基础。
- 保留 Phase 1–2C Runtime，不重写已验证能力。
- 建立 OpenAPI/Schema 的兼容策略。

### Phase 3C：PostgreSQL Task/Run 与 API/Worker

状态：`TODO`

目标：

- PostgreSQL Task/Run/Step/Checkpoint/ToolCall/Outbox。
- health-agent-api 和 health-agent-worker。
- lease/fence/checkpoint 从 JSON 迁移到生产存储。
- Redis Streams Queue Port 和 PostgreSQL reconciler。

### Phase 3D：Health Platform 业务权威和 Tool API

状态：`TODO`

目标：

- User、Conversation、Message、Fact、Goal 和审计。
- Platform → Agent Task 合同。
- Agent → Platform Read Tool API。
- mTLS + 短期 JWT 最小闭环。

### Phase 3E：Plan、Revision、风险和确认

状态：`TODO`

目标：

- Plan/PlanVersion/PlanItem/ExecutionRecord。
- 候选、整体确认、局部修改、revision 和冲突。
- RiskFinding、二次确认和审计。
- 终止、预算追加和 PendingAction 产品闭环。

### Phase 3F：文件、MinIO 和逐项事实确认

状态：`TODO`

目标：

- ObjectStorageProvider + MinIO。
- 上传、扫描、Sandbox 解析。
- FileExtractionCandidate 逐项确认。
- 文件彻底删除和 RAG 失效。

### Phase 3G：Context、RAG、Sub-Agent 和模型预算

状态：`TODO`

目标：

- 结构化 Summary 和校验。
- PostgreSQL + pgvector。
- reranker fallback。
- 一层顺序 Sub-Agent。
- Provider fallback 和预算续期。

### Phase 3H：Sandbox、Secret 和安全加固

状态：`TODO`

目标：

- Tool 执行策略。
- Sandbox 网络/文件/资源隔离。
- Health Platform SecretService 和短期签发。
- 跨用户、重放、SSRF 和日志脱敏测试。

### Phase 3I：Kubernetes、可观测性和高可用

状态：`BLOCKED`

阻塞：

- Kubernetes 发行版、CNI、Ingress、证书管理、PostgreSQL Operator 和 Redis 拓扑需技术 Spike/ADR。

目标：

- 6 VM K8s 集群。
- 应用和有状态组件部署。
- OTel、Prometheus、Grafana、Loki、Alertmanager。
- 灰度、Worker 排空、故障转移和容量告警。

### Phase 3J：生产验收和故障演练

状态：`TODO`

目标：

- 业务闭环。
- 故障恢复。
- 安全测试。
- 数据一致性。
- 运维、备份恢复和灰度证据。

只有 Phase 3J 全部完成后，产品才能标记为生产可用。

## 6. 已知风险

| 风险 | 当前决定 |
|---|---|
| 单 Hyper-V 宿主机 | 接受；不能声明跨主机 HA |
| 单物理 SSD | 接受；保留容量余量并持续告警 |
| 无 NAS/云外部备份 | 接受先上线；管理端持续高风险提示 |
| 医学阈值未专业审核 | 标记 `NEEDS_MEDICAL_REVIEW`，不得自行实现 |
| Phase 3B Slice 1 legacy 清理 | Java 后端及其客户端/部署耦合已删除；骨架不等于业务完成 |
| 当前 Runtime 是 CLI/JSON | 仅 Phase 1–2C 实现事实，不等于生产服务 |

## 7. 进入实施的强制条件

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

## 8. 提示词约束

后续由 ChatGPT 生成的任何 Codex/Trae/Hermes/Claude Code 提示词必须：

- 引用对应权威文档。
- 不重复发明架构。
- 不提前实现后续 Phase。
- 不放宽状态机、安全、幂等和验收。
- 要求完成报告写回本文件。

不满足以上条件的提示词视为无效。
