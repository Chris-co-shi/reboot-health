# 系统架构（FROZEN）

## 1. 架构结论

目标系统由两个独立部署、职责明确的核心服务组成：

```text
Web 用户端 / 微信小程序 / Flutter / Vue Admin
                     ↓
               Health Platform
                     ↓  内部 HTTPS + mTLS + 短期 JWT
                 health-agent
                     ↓
        Model Provider / Tool / Sandbox / Runtime Store
```

- **Health Platform**：业务平台、数据权威和控制面。
- **health-agent**：通用 Agent 执行层，不承载健康业务权威和用户 RBAC。

当前仓库中 `health_agent/` 的 Phase 1–2C 代码是未来 `health-agent` 服务的迁移基础；它当前仍是本地 Python Runtime，不代表目标服务已经生产化。

ADR 0023 调整 Phase 3/4 实施边界和客户端顺序，但不改变双服务、Platform 业务权威、Agent 通用执行和客户端只访问 Platform 的架构结论。

## 2. 客户端职责和顺序

```text
clients/web/       ─┐
clients/miniapp/   ─┤
clients/flutter/   ─┼→ Health Platform Public API
frontend/          ─┘

Health Platform → health-agent Internal API
health-agent → Health Platform Internal Tool API
```

- `clients/web/` 是 Phase 4 首个普通用户业务验证入口，当前只存在于规划中。
- `clients/miniapp/` 和 `clients/flutter/` 在 Web 闭环稳定后接入，并复用同一业务合同。
- `frontend/` 是 Vue 3 管理、运维、诊断和审计端，不承担普通用户健康业务。
- 平台差异只允许出现在登录适配、通知、深链、本地存储和设备能力，不得产生不同业务权威。
- health-agent API 不暴露公网，只允许内部网络和受信服务身份。
- 任何客户端不得直接调用 health-agent、数据库、Redis、MinIO 或 Tool handler。

## 3. Health Platform 职责

Health Platform 使用 Python 实现，负责：

- 用户身份、登录、业务权限和设备会话。
- 用户可见 Conversation、Session 和 Message。
- UserProfile、Fact、Goal 和 Readiness。
- HealthProgram、ProgramVersion、TrainingPlan、RecoveryPlan、NutritionPlan。
- Plan Revision、Execution Record、Check-in、Feedback 和 AdjustmentCandidate。
- Risk、用户确认、历史纠错和业务审计。
- ReminderTask、通知偏好和确定性调度权威。
- File 元数据、ObjectStorageProvider、MinIO、上传和删除。
- Secret 管理、加密存储、临时凭证签发和访问审计。
- 对客户端提供正式 API 和 SSE。
- 为 health-agent 提供内部 Tool REST API。
- 创建 Agent Task，维护本地 Task 投影，接收回调并执行补偿拉取。
- 汇总 health-agent 管理信息给 Vue 管理端。

Health Platform 是所有健康业务事实、用户决定、文件归属、综合计划、执行记录和正式通知任务的唯一权威。

Phase 4 尚处于 `DISCOVERY`，以上健康业务对象是目标职责，不代表当前代码已经实现。

## 4. health-agent 职责

health-agent 是独立、可横向扩展的通用执行服务，负责：

- Agent Task、Run、Step、Checkpoint 和 ToolCall 技术状态。
- Model Turn、Tool Call Loop、预算、超时、错误收敛和 Provider fallback。
- lease、heartbeat、fencing、防重复执行和 stale recovery。
- Context 组装、压缩、RAG、Sub-Agent 和结构化结果校验。
- Sandbox 调度和不可信文件/代码执行隔离。
- 运行事件、Trace、Outbox 和管理查询。
- 生成 Fact、Goal、Program、Adjustment 和 Risk 的结构化候选。

health-agent 不负责：

- 用户登录和用户级 RBAC。
- 直接连接 Health Platform 数据库。
- 定义或修改正式健康事实。
- 直接发布正式 Program/Plan。
- 直接创建生效的 ReminderTask。
- 保存长期业务 Memory。
- 代表用户确认风险、计划或副作用。
- 降低确定性风险规则的结果。

## 5. 进程形态

同一 health-agent 代码库和镜像至少支持两个进程角色。

### 5.1 health-agent-api

- 创建 Task。
- 查询 Task/Run 状态。
- 接收用户补充输入。
- 终止当前 Run。
- 提供事件、回放和快照接口。
- 不执行模型和 Tool 主循环。

### 5.2 health-agent-worker

- 从调度队列领取工作。
- 获取 lease 和 fence generation。
- 执行模型、Tool、Sub-Agent、RAG 和 Checkpoint。
- 续约 heartbeat。
- 处理安全恢复、预算耗尽和副作用分类。

API 和 Worker 作为不同 Deployment 运行，可使用同一镜像和不同启动命令。

## 6. Task、Run 和异步执行

### 6.1 核心定义

- **Task**：一个连续用户目标，可经历多次执行尝试。
- **Run**：Task 的一次执行尝试。
- **Step**：Run 中可检查、可恢复的执行单元。

一次 Run 可以进入 `WAITING_USER_INPUT` 或 `WAITING_CONFIRMATION` 并在同一 Run 内继续；只有正式失败、终止或预算耗尽后再次执行才创建新 Run。

### 6.2 底层形态

```text
客户端 POST 消息
→ Health Platform 持久化业务消息
→ 创建 Agent Task
→ health-agent-api 持久化 Task/Run
→ PostgreSQL 事务提交
→ 调度信号进入 Redis Streams
→ Worker 领取、lease、执行、checkpoint
→ Outbox 产生事件
→ 回调 Health Platform
→ SSE 推送客户端
```

客户端断开连接不取消执行。

## 7. 数据存储和调度

### 7.1 PostgreSQL

PostgreSQL 是权威持久化层，保存：

- Health Platform 业务数据。
- health-agent Task、Run、Step、Checkpoint、ToolCall、PendingAction、Outbox。
- RAG 元数据和 pgvector 向量。
- Inbox、幂等记录、版本和审计。

Platform 和 health-agent 使用逻辑隔离的数据库、Schema 和账号；禁止跨服务直接访问对方表。

### 7.2 Redis

Redis 是调度和协调加速层，不是业务权威：

- Redis Streams 工作调度。
- consumer group、重试和 wake-up 信号。
- lease/heartbeat 协调、速率计数和短期缓存。

Redis 丢失、重复或延迟消息时，PostgreSQL reconciler 必须识别待执行任务并重新入队；fencing 阻止旧 Worker 继续写入。

第一版不引入 RabbitMQ，但 Publisher/Queue Port 必须允许未来替换。

## 8. Platform 与 Agent 状态同步

health-agent 的执行状态是 Agent 执行权威，Health Platform 保存面向业务和客户端的本地投影。

采用：

```text
Transactional Outbox
+ HTTP Callback
+ Platform Inbox Idempotency
+ 序号缺口检测
+ 事件重放 / Snapshot Pull
+ 周期 Reconciler
```

语义是 **at-least-once + 幂等消费 + 缺口检测 + 对账**，不得声称 exactly-once。

事件至少包含：

```text
eventId
taskId
runId（可选）
sequence
eventType
occurredAt
payloadVersion
payloadHash
traceId
```

重复事件通过 `eventId` 唯一约束处理；序号缺口触发 pull；失败回调重试并进入 dead-letter 状态但不得静默删除。

## 9. Agent Task 合同

Health Platform 创建 Task 时只传递最小合同：

```text
platformTaskId
sessionId
userId
messageId
userMessage
delegationToken
traceId
```

Platform 不预判并下发完整 `allowedCapabilities`。Agent 动态决定需要调用哪些 Tool；每次 Tool 调用由 Health Platform 根据用户、Task、Run、数据归属、业务状态、Tool Scope 和短期凭证实时校验。

Phase 4 的详细 Program、Fact、Goal 或 Nutrition 字段不得直接塞入 Task 技术合同；Agent 应通过受控 Tool 读取当前权威数据。

## 10. Tool 架构

Tool 必须通过 Registry 白名单注册，并声明：

```text
name
inputSchema
outputSchema
executionMode
riskLevel
networkPolicy
filesystemPolicy
secretRefs
timeout
resourceLimits
sideEffect
idempotency
compensationPolicy
```

Tool 分类：

- Platform Read Tool：同步读取已确认业务事实。
- Platform Write Candidate Tool：只能创建草案、候选事实、风险发现、纠错请求或变更请求。
- Sandbox Tool：文件解析、代码/命令、第三方不可信内容和受限网络访问。

任何 Tool 都不能直接绕过 Platform 使正式业务数据生效。

## 11. 身份、授权和服务信任

- 人类账号角色首版仅为 `USER` 和 `ADMIN_OPERATOR`。
- `SERVICE_HEALTH_AGENT` 是独立服务主体，不是人类账号角色。
- 所有业务对象必须具备 `userId` 或等价归属边界。
- 客户端访问使用用户 Session/OAuth Token。
- Platform → Agent 使用 mTLS 和短期 Task 凭证。
- Agent → Platform Tool API 使用 mTLS 和短期 Tool Scope 凭证。
- 凭证至少绑定 audience、subject、user、Task/Run、Scope、jti、iat 和 exp。
- 未知角色、Scope、主体类型、过期凭证、重放和跨用户访问全部 fail-closed。

完整规则见 `SECURITY_AND_PRIVACY.md` 和 ADR 0022、0023。

## 12. Context 压缩

采用混合触发：

- 语义节点：等待用户、候选 Program 完成、Sub-Agent 返回、Run 切换或阶段完成。
- token soft threshold：约 60%–70%。
- token hard threshold：约 80%–85%，并动态预留输出和 Tool token。

模型上下文由以下部分组成：

```text
经过验证的结构化 Summary
+ 少量最近原始消息
+ 强制关键消息
+ 相关历史检索结果
+ 通过 Platform Tool 实时读取的当前权威事实
```

必须强制保留当前请求、未消费消息、最新纠正、待回答问题、待确认候选、风险确认和当前 Checkpoint。

Summary 由模型生成候选，Runtime 校验 Schema、引用、版本、待办项和 token budget。失败时依次：同模型重试、备用模型、沿用旧 Summary；接近硬上限且均失败时进入人工处理。

## 13. RAG

第一版使用 PostgreSQL + pgvector，并通过接口保留迁移到外部向量库的可能。

可索引：

- 用户可见业务对话。
- 已验证结构化 Summary。
- 脱敏、裁剪后的关键 Tool 证据。

不可索引：

- 系统 Prompt、开发指令和隐藏推理。
- Secret、Token、完整敏感 Tool 原始结果。
- 未验证模型猜测。
- 已失效、已删除或其他用户数据。

默认只检索当前 Session。需要历史时，主模型显式请求扩展到同一用户其他 Session。纠正或删除发生时同步标记 Chunk 失效并立即排除，异步执行删除、重切片和重嵌入。

检索链路：

```text
权限与 metadata 硬过滤
→ pgvector 候选
→ 确定性混合评分
→ 专用 reranker
→ token budget 裁剪
```

reranker 不可用时退化为确定性评分；复杂冲突任务可使用 LLM rerank，但 LLM 只能看到已经授权和有效的候选。

## 14. Sub-Agent

- 主 Agent 按需创建 Sub-Agent。
- 第一版顺序执行，不做并行 DAG。
- 委派深度最多 1。
- Sub-Agent 获取 Task/Run/SubTask 绑定的短期凭证和最小 Tool Scope。
- 输出必须包含结构化结果、sourceRefs、assumptions、uncertainties 和 completionStatus。
- Runtime 校验 Schema、引用存在性、用户归属和有效性。
- 主 Agent 可接受、部分采用、要求一次返工或拒绝。
- Sub-Agent 结果不能直接成为正式事实或正式 Program。

## 15. 文件架构

```text
客户端申请上传
→ Health Platform 校验用户、配额和类型
→ 返回短期签名上传 URL
→ 客户端上传 ObjectStorageProvider
→ Platform 校验大小、Hash、MIME 和扫描状态
→ AVAILABLE
→ health-agent 通过 Tool 获取短期只读 URL
→ Sandbox 解析
→ 生成逐项待确认 Extraction Candidate
```

第一版 `ObjectStorageProvider` 实现为 MinIO；未来可迁移到 S3、OSS 或 COS，不改变业务模型和 Agent Tool 合同。

文件能力的具体实施阶段由后续路线决定，不因 Phase 4 产品基线自动进入代码实施。

## 16. 模型路由和预算

- 普通回答、Summary 和 RAG rerank 可自动 fallback。
- Program 和风险关键阶段允许 fallback，但确认页必须记录模型切换。
- fallback 模型必须支持必要 Tool、Schema 和上下文长度，且不能扩大权限。
- 每个 Run 有全局硬上限和按任务类型默认预算。
- 预算覆盖模型次数、输入/输出 token、运行时间、Tool、Sub-Agent、RAG、Sandbox 和估算成本。
- 预算耗尽时旧 Run 进入 `BUDGET_EXHAUSTED`；用户批准追加预算后创建新 Run，从安全 Checkpoint 继续并重新验证版本。

## 17. 风险与确定性边界

- 身份、权限、归属、版本、幂等和状态机由程序保证。
- Phase 4 风险采用 R0–R4 确定性分级。
- Agent 可以识别上下文、解释、追问和提出更高风险候选。
- Agent 不得降低确定性风险等级。
- 医学阈值未专业审核时标记 `NEEDS_MEDICAL_REVIEW`。
- 高风险可以暂停受影响的未来任务，但不能静默发布新 Program。

## 18. Reminder 架构

```text
Confirmed DailySchedule
→ Health Platform 创建 ReminderTask
→ 确定性调度器处理时区、免打扰、幂等、延后、过期和有限重试
→ Agent 可生成个性化文案
→ 正式通知渠道发送
```

ReminderTask 和通知偏好属于 Health Platform 业务权威。Agent 文案不能修改任务语义、时间规则或安全边界。

具体通知渠道和供应商尚未冻结。

## 19. 可观测性

统一使用：

- OpenTelemetry traces、metrics、log correlation。
- Prometheus。
- Grafana。
- Loki。
- Health Platform 业务审计。

关联标识：`traceId`、`taskId`、`runId`、`stepId`、`toolCallId` 和脱敏 `userId`。

日志不得保存完整健康原文、完整 Prompt、Secret、Token 或完整敏感 Tool 响应。

## 20. 当前实现迁移规则

Phase 1–2C 已完成的 Runtime 能力必须作为迁移输入，而不是被重新发明：

- OpenAI-compatible Provider。
- 通用 Tool Call Loop。
- Session Message History。
- Confirmation 基础合同。
- JSON Store、CAS、lease、heartbeat、fencing。
- execution checkpoint、stale recovery、orphan maintenance。
- interactive CLI。

迁移到 PostgreSQL、API/Worker 和 Kubernetes 时必须保持既有测试语义，并用新的持久化和分布式验收替代本地 JSON 的生产职责。

## 21. Health Platform 内部形态

Health Platform 是独立服务内部的 Python 3.12 模块化单体，不恢复全系统单体：

```text
FastAPI + lifespan 管理后台线程
SQLAlchemy 2 同步 Session + psycopg 3
单一 PostgreSQL（模块独立 Schema）
Redis 短 TTL 非权威缓存
```

业务按纵向模块组织，Domain/API DTO/SQLAlchemy Model 分离。写用例经 UoW 一次提交；Audit/Outbox 与业务同事务，外部 I/O 在提交后执行。每 Pod 的非 daemon 后台线程以 PostgreSQL 原子抢占协调多副本，不引入 Celery、RabbitMQ 或独立 Platform Worker。

## 22. Phase 3/4 实施边界

### Phase 3

- 生产基础与 Identity。
- 用户归属和服务间授权。
- health-agent 生产 Runtime。
- 安全、恢复和基础验收。

### Phase 4

- Fact、Goal 和 Readiness。
- HealthProgram 与训练、恢复、饮食计划。
- Execution、Feedback、Adjustment、Risk 和 Reminder。
- 独立 Web 用户端完整闭环。

Phase 4 当前为 `DISCOVERY`。本架构文档中的目标对象不代表可以跳过 `READY`、implementation specification、迁移和验收直接实施。