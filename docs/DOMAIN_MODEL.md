# 领域模型（FROZEN）

## 1. 建模原则

- Health Platform 是健康业务数据和用户决定的唯一权威。
- health-agent 的 Session、Task、Run、Step、Summary 和 Tool Result 是执行技术状态，不自动成为业务事实。
- AI 输出、OCR 和文件解析结果默认是候选。
- 所有模型必须具备明确 `userId` 或等价归属边界。
- 已完成执行和历史审计不可被后续 Plan 或模型理解静默改写。
- 业务对象使用版本、状态、来源和审计表达变化，不做无痕覆盖。

## 2. 用户与会话

### User

用户身份和数据归属根。第一阶段只有一个真实用户，但数据库、API、Token 和所有业务聚合必须按 `userId` 隔离。

### ConversationSession

用户可见的连续对话容器，由 Health Platform 管理。

包含：

- `sessionId`
- `userId`
- 标题和状态
- 创建、最后活动和关闭时间
- 当前活跃 Task 引用（可选）

Session 关闭或删除不自动删除健康事实、Plan、执行记录或审计。

### ConversationMessage

用户、assistant 和产品事件的完整用户可见消息。

- 原始用户消息由 Health Platform 长期保存，按数据保留策略删除。
- 内部 system prompt、隐藏推理和完整 Tool 原始结果不属于用户可见 Message。
- `messageSequence` 在同一 Session 内单调递增。

## 3. Fact 体系

### HealthFact

经确认的当前业务事实，例如：

- 身高、体重和体征。
- 目标、偏好和器械条件。
- 健康限制和专业建议记录。
- Observation 和执行反馈。

核心字段语义：

```text
factId
userId
factType
value / structuredPayload
sourceType
sourceRef
validFrom / validTo
status
version
confirmedBy
confirmedAt
supersededBy
```

### FactCandidate

来自用户消息、模型、文件解析或 Tool 分析的待确认候选。

- 不能参与正式业务写入和 Plan 发布，除非界面明确标识为“未确认候选”。
- 文件提取的所有健康字段必须逐项确认。
- 候选可以被确认、修改后确认、拒绝、失效或被新候选替代。

### FactRevision

保存历史纠正事件：

- 原事实和值。
- 新事实和值。
- 纠正原因和来源。
- 用户二次确认记录。
- 影响分析摘要。

后确认的有效事实成为当前值，旧事实进入 `SUPERSEDED`，但不物理消失。

## 4. Goal

Goal 表达用户希望达到的结果，不直接等于 Plan Item。

- 保留用户原始表达和结构化成功标准。
- 允许结构化指标为空，禁止为完整性虚构值。
- Goal 修改需要版本和审计。
- 模型只能生成 GoalCandidate；确认后才成为 Goal。

## 5. Plan 体系

### Plan

长期计划身份，为当前生效计划和历史版本提供稳定归属。

### PlanVersion

一次完整候选或已发布计划快照。

语义：

- `CANDIDATE`：Agent 或用户生成，等待确认。
- `CONFIRMED`：用户确认后正式生效。
- `SUPERSEDED`：被新确认版本替代。
- `ABANDONED`：Run 被终止、关键 Fact 改变或用户放弃后不可确认。
- `REJECTED`：用户明确拒绝。

不变量：

- 一个 Plan 同一时刻最多有一个当前 `CONFIRMED` 版本。
- 新候选未确认前旧版本继续有效。
- 候选确认必须校验 `expectedRevision`、事实版本和风险确认状态。
- 已确认版本不可原地覆盖；修改产生内部 Revision 或新 PlanVersion。

### PlanItem

计划中的可执行条目，包含目标、动作、时间/频率、完成定义、安全说明和可调整范围。

### PlanRevision

记录当前 Plan 未完成部分的变更：

- before/after。
- 影响的 PlanItem。
- 变更发起者：用户或 Agent。
- 触发 Fact、风险检查和确认记录。
- 乐观锁 revision。

用户直接发起且通过确定性检查的低风险变更可立即作用于未完成部分；Agent 主动提出的变更必须先形成候选。

### ExecutionRecord

用户实际完成、部分完成、跳过或中止的历史事实。

- 不因 Plan 修改而改变。
- 允许显式历史纠错，但必须二次确认并保留修订记录。
- Plan 的完成状态通过 ExecutionRecord 推导，不通过覆盖 PlanItem 历史表达。

## 6. Risk 体系

### RiskFinding

系统或 Agent 对已完成行为、候选 Plan、未来调整或数据冲突识别出的风险。

包含：

```text
riskId
userId
sourceTaskId
subjectType / subjectId
severity
summary
evidenceRefs
saferAlternatives
status
```

### RiskAcknowledgement

用户对风险说明的二次确认：

- 展示内容版本。
- 用户选择。
- 时间和设备。
- 最终应用的变更版本。

RiskFinding 不能修改历史执行事实；它只影响候选、提醒和后续决策。

## 7. Agent 执行模型

### AgentTask

一个连续用户目标。

- 由 Health Platform 的 `platformTaskId` 与 health-agent Task 一一关联。
- 可以包含多个 Run。
- 继续补充信息通常仍属于同一 Task。
- 候选 Plan 已进入确认后，新的修改请求可以产生新 Run 或新的 Revision Task。

### AgentRun

Task 的一次执行尝试。

包含：

```text
runId
taskId
attempt
status
budget
owner / lease / fenceGeneration
checkpointVersion
startedAt / endedAt
failureClassification
previousRunId（可选）
```

### AgentStep

Run 中的可检查执行单元：

- Context 组装。
- Model Call。
- Tool Call。
- Sub-Agent。
- RAG。
- Finalization。

每个 Step 有输入引用、输出引用、状态、重试次数和时间信息，但不得把完整 Secret 或敏感原文写入日志字段。

### ExecutionCheckpoint

用于恢复的持久快照，至少记录：

- 当前 Run/Step。
- 可恢复位置。
- 已消费消息序号。
- 当前 Summary 版本。
- 已完成 ToolCall 引用。
- 等待原因。
- fence generation。

### PendingAction

只用于需要用户或管理员明确决定的高影响动作：

- Plan 确认。
- 风险确认。
- 历史纠错确认。
- 追加预算。
- 无法自动处理的副作用。

普通澄清问题不是 PendingAction。

## 8. Tool 和副作用模型

### ToolDefinition

工具的稳定合同和执行策略。

### ToolCall

一次具体调用，包含 `toolCallId`、Tool 版本、参数摘要、结果引用、风险、幂等键、状态和审计。

### SideEffectRecord

仅对可能产生外部或业务副作用的 Tool 建立：

- effectType。
- idempotencyKey。
- preconditionVersion。
- resultRef。
- compensationTool 和状态。
- outcome certainty。

只有明确幂等且结果可证明的操作允许自动重试。结果不确定或不可幂等时进入人工处理。

## 9. Sub-Agent 模型

### SubTask

主 Agent 创建的最小委派单元。

包含：

```text
subTaskId
taskId
runId
goal
allowedToolScope
expiresAt
delegatedBy
delegationDepth = 1
status
```

### SubAgentResult

结构化结果：

- `result`
- `sourceRefs`
- `assumptions`
- `uncertainties`
- `completionStatus`
- 主 Agent review 结论

SubAgentResult 不是正式业务事实。

## 10. Context 与 RAG 模型

### ConversationSummary

经过 Runtime 校验的上下文压缩结果。

至少包含：

```text
summaryVersion
previousVersion
basedOnMessageSequence
basedOnCheckpointVersion
generatedByModel
schemaVersion
createdAt
validationStatus
```

Summary 不得标记未确认内容为已确认，也不能覆盖正式 Fact。

### RagDocument / RagChunk

非权威历史检索索引。

关键 metadata：

```text
sourceType
sourceId
userId
sessionId
taskId
contentVersion
validStatus
sensitivity
createdAt
supersededBy
embeddingModelVersion
```

失效或删除后必须立即从检索过滤，再异步物理删除和重建。

## 11. File 模型

### FileAsset

Health Platform 管理的文件权威元数据。

包含：

```text
fileId
userId
objectKey
objectVersion
originalName
mimeType
size
checksum
businessPurpose
status
scanStatus
createdAt
```

原始文件本体由 ObjectStorageProvider 管理，不写入 PostgreSQL 大字段。

### FileDerivative

缩略图、OCR、解析文本和结构化中间产物，与原文件版本绑定。

### FileExtractionCandidate

从文件中提取的单个待确认健康字段，必须包含页码/区域/原文引用、值、单位、置信信息和状态。

### FileDeletionRequest

用户发起彻底删除的业务对象。删除成功后仅保留不含文件内容的删除审计。

## 12. 事件、幂等和审计

### OutboxEvent

服务本地事务内生成的待发布事件。

### InboxRecord

接收方按 `eventId` 幂等消费，并记录 sequence。

### IdempotencyRecord

高影响 POST、Tool 写候选和回调使用稳定幂等键。相同 key + 相同规范化请求返回第一次结果；相同 key + 不同请求必须失败。

### AuditRecord

只追加记录：

- actor。
- action。
- entityType/entityId。
- before/after 摘要或引用。
- reason。
- traceId。
- createdAt。

审计不得保存 Secret、完整 Prompt、隐藏推理或不必要的完整健康原文。

## 13. 数据权威矩阵

| 数据 | 权威服务 |
|---|---|
| 用户、Conversation、Message | Health Platform |
| HealthFact、Goal、Plan、Execution、Risk | Health Platform |
| FileAsset、删除和提取确认 | Health Platform |
| Secret 配置、版本和签发审计 | Health Platform |
| Task/Run/Step/Checkpoint/ToolCall | health-agent |
| 执行状态投影 | Health Platform 投影，health-agent 为执行权威 |
| ConversationSummary | health-agent 执行数据，不能成为业务事实 |
| RAG 索引 | 技术派生数据，源数据权威仍在 Platform |

## 14. 禁止的重复事实源

禁止建立：

- 与 PlanVersion 并行的第二套正式发布引擎。
- 与 HealthFact 并行的“模型记忆事实表”。
- health-agent 自己维护的长期用户画像。
- MinIO object metadata 代替 Platform FileAsset。
- Redis 状态代替 PostgreSQL Task/Run 权威。
- 前端本地状态代替服务端 revision 和确认记录。

## 15. Identity、Audit 与后台对象

- `UserAccount`：邮箱/用户名规范化标识、展示名、状态、邮箱验证、权限版本和锁定信息。
- `IdentitySession`：一次设备登录，绑定客户端、设备摘要、最近活动与撤销时间。
- `TokenFamily` / `RefreshToken`：每设备独立轮换链；旧 Token 重放撤销整个 Family。
- `EmailVerification` / `PasswordRecovery` / `AuthorizationCode`：短期、一次性，数据库只保存 Token 哈希。
- `MfaEnrollment` / `RecoveryCode`：TOTP Secret 加密，恢复码哈希且一次性。
- `RoleAssignment`：人类账号仅允许 `USER` 与 `ADMIN_OPERATOR`；服务主体通过 Principal/Actor Kind 表达，禁止进入用户角色集合。本 Slice 不实现通用 RelationshipGrant 或 ABAC。
- `AuditEvent`：只追加、前一哈希连接，不记录 Secret 或完整敏感内容。
- `OutboxEvent`：PENDING/PROCESSING/PUBLISHED/FAILED，支持锁租约、退避、恢复和幂等事件 ID。
- `ExportJob` / `AccountDeletionRequest`：Identity 范围任务；跨模块导出/删除由后续模块扩展，不能伪造完成。
