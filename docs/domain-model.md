# 领域模型

## 1. 建模原则

- 先保证计划闭环和安全不变量，再扩展训练内容库。
- 计划、执行、分析、AI 建议、用户确认必须分离。
- 历史执行记录是事实，不能随计划版本变化。
- AI 输出是建议，不是领域事实。
- 医疗相关内容只作为约束、提醒和风险信息，不生成诊断结论。
- MVP 不为简单字段创建无业务行为的包装类；ID 使用 `UUID`，数值使用 `BigDecimal`，名称和标题使用 `String`。

## 2. M2A 聚合

### UserProfile

个人档案聚合，保存单人应用的基础档案。

字段：

- `id: UUID`
- `displayName: String`
- `sex: Sex`
- `birthDate: LocalDate`
- `heightCm: BigDecimal`
- `baselineWeightKg: BigDecimal?`
- `timezone: String`
- `createdAt: Instant`
- `updatedAt: Instant`

规则：

- 单人应用只允许一个当前档案。
- `baselineWeightKg` 只表示建立档案时的基线体重，可为空。
- 不保存 `currentWeightKg`。
- M3 后当前体重必须从最新 `BodyMetricEntry` 查询。
- 业务页面不得把 `baselineWeightKg` 展示为实时当前体重。

### HealthConstraint

健康约束聚合，表达用户手动维护的训练限制、风险提醒和注意事项。

字段：

- `id: UUID`
- `constraintType: ConstraintType`
- `bodyRegion: BodyRegion`
- `severity: ConstraintSeverity`
- `title: String`
- `description: String`
- `sourceType: ConstraintSourceType`
- `sourceNote: String?`
- `status: ConstraintStatus`
- `effectiveFrom: LocalDate?`
- `effectiveTo: LocalDate?`
- `archiveReason: String?`
- `createdAt: Instant`
- `updatedAt: Instant`
- `archivedAt: Instant?`

规则：

- AI 不能删除、停用或弱化健康约束。
- M2A 允许用户手动创建、修改、停用、解决和归档。
- 普通状态变更不能执行归档；归档必须走专用方法并提供原因。
- 归档不物理删除。
- 归档后禁止普通编辑和状态变更。
- 不存储由系统推断出的医学诊断结论。

### Goal

目标聚合，表达体重、腰围、训练习惯、有氧能力、力量、游泳、篮球体能和睡眠等目标。

字段：

- `id: UUID`
- `goalType: GoalType`
- `title: String`
- `targetValue: BigDecimal?`
- `unit: GoalUnit`
- `baselineValue: BigDecimal?`
- `targetDate: LocalDate?`
- `status: GoalStatus`
- `priority: Integer`
- `archiveReason: String?`
- `createdAt: Instant`
- `updatedAt: Instant`
- `archivedAt: Instant?`

规则：

- 目标不是计划任务。
- 目标不直接包含每日训练动作。
- 只有 `ACTIVE` 和 `PAUSED` 目标允许编辑内容。
- `COMPLETED`、`CANCELLED` 和 `ARCHIVED` 为终态，不恢复为进行中。
- 已完成或已取消的目标如需重新开始，应创建新目标。
- 普通状态变更不能执行归档；归档必须走专用方法并提供原因。

## 3. 枚举

`Sex`：`MALE`、`FEMALE`、`OTHER`、`UNSPECIFIED`

`ConstraintType`：`HYPERTENSION`、`CERVICAL_LIMITATION`、`SHOULDER_NECK_DISCOMFORT`、`LOWER_BACK_STRAIN`、`HIP_MOBILITY_LIMITATION`、`FOOT_SOLE_ISSUE`、`ACHILLES_DISCOMFORT`、`FORBIDDEN_MOVEMENT`、`TRAINING_PRECAUTION`、`OTHER`

`BodyRegion`：`CARDIOVASCULAR`、`CERVICAL_SPINE`、`SHOULDER_NECK`、`LOWER_BACK`、`HIP`、`FOOT_SOLE`、`ACHILLES_TENDON`、`FULL_BODY`、`OTHER`

`ConstraintSeverity`：`INFO`、`LOW`、`MEDIUM`、`HIGH`、`CRITICAL`

`ConstraintSourceType`：`USER_REPORTED`、`DOCTOR_ADVICE`、`MEDICAL_REPORT`、`MEASUREMENT`、`OTHER`

`ConstraintStatus`：`ACTIVE`、`INACTIVE`、`RESOLVED`、`ARCHIVED`

`GoalType`：`WEIGHT`、`WAIST`、`TRAINING_HABIT`、`AEROBIC_CAPACITY`、`STRENGTH`、`SWIMMING`、`BASKETBALL_CONDITIONING`、`SLEEP`、`OTHER`

`GoalStatus`：`ACTIVE`、`PAUSED`、`COMPLETED`、`CANCELLED`、`ARCHIVED`

`GoalUnit`：`KG`、`CM`、`SESSIONS_PER_WEEK`、`MINUTES`、`MINUTES_PER_DAY`、`METERS`、`LAPS`、`REPETITIONS`、`SECONDS`、`SCORE`、`PERCENT`、`NONE`

## 4. 状态流转

### HealthConstraint

| 当前状态 | 普通状态变更允许目标 |
|---|---|
| ACTIVE | INACTIVE, RESOLVED |
| INACTIVE | ACTIVE, RESOLVED |
| RESOLVED | 无 |
| ARCHIVED | 无 |

归档允许来源：`ACTIVE`、`INACTIVE`、`RESOLVED`。归档只能通过专用 `archive` 方法。

状态语义：

- `ACTIVE`：当前有效，必须进入后续规则引擎和 AI 当前上下文。
- `INACTIVE`：用户暂时停用，不参与规则判断；可作为历史信息进入 AI 上下文，但必须明确标记为非当前约束。
- `RESOLVED`：问题已解决或不再需要当前限制，不参与规则判断；M2A 不允许重新激活。
- `ARCHIVED`：用户主动归档，默认列表不显示，不参与规则和 AI 当前上下文，禁止普通编辑和状态变更，M2A 不实现恢复。

### Goal

| 当前状态 | 普通状态变更允许目标 |
|---|---|
| ACTIVE | PAUSED, COMPLETED, CANCELLED |
| PAUSED | ACTIVE, COMPLETED, CANCELLED |
| COMPLETED | 无 |
| CANCELLED | 无 |
| ARCHIVED | 无 |

归档允许来源：`ACTIVE`、`PAUSED`、`COMPLETED`、`CANCELLED`。归档只能通过专用 `archive` 方法。

状态语义：

- `ACTIVE`：正在执行。
- `PAUSED`：暂停执行，未来可以恢复。
- `COMPLETED`：已完成，终态。
- `CANCELLED`：已取消，终态。
- `ARCHIVED`：隐藏保留，终态。

## 5. Goal 单位规则

- `WEIGHT`：`KG`
- `WAIST`：`CM`
- `TRAINING_HABIT`：`SESSIONS_PER_WEEK`
- `SWIMMING`：`METERS`、`LAPS`、`MINUTES`
- `STRENGTH`：`KG`、`REPETITIONS`、`SECONDS`、`SCORE`
- `AEROBIC_CAPACITY`：`MINUTES`、`METERS`、`SCORE`
- `BASKETBALL_CONDITIONING`：`MINUTES`、`REPETITIONS`、`SCORE`
- `SLEEP`：`MINUTES`、`MINUTES_PER_DAY`
- `OTHER`：`NONE` 或其他明确单位

除 `OTHER + NONE` 外：

- `targetValue` 必填且必须大于或等于 0。
- `baselineValue` 可为空；存在时必须大于或等于 0。
- `unit` 和 `goalType` 必须匹配。

`OTHER + NONE`：

- `targetValue` 必须为空。
- `baselineValue` 必须为空。
- 允许用标题表达文字目标。

## 6. M2B 计划聚合

### Plan

长期计划身份。MVP 只维护一个当前 Plan，周期内容全部由 PlanVersion 表达。

字段：

- `id: UUID`
- `title: String`
- `summary: String?`
- `createdAt: Instant`
- `updatedAt: Instant`

### PlanVersion

7 天计划周期版本。

状态：

- `DRAFT`：可编辑、可取消、可确认。
- `CONFIRMED`：已确认，不可修改；可以是历史、当前或未来周期。
- `SUPERSEDED`：同一日期周期旧确认版本被新确认版本替代，不可修改。
- `CANCELLED`：已取消草案，不可修改。

规则：

- 不使用 `ACTIVE` 状态。
- 当前计划通过 `CONFIRMED` 且 `startDate <= currentDate <= endDate` 计算，`currentDate` 必须按 `UserProfile.timezone` 得出；档案不存在时使用显式 `app.default-timezone`，不得使用 JVM 默认时区。
- 每个周期固定 7 天，`endDate = startDate + 6`。
- `versionNumber` 是同一 Plan 下全局递增版本号。
- `periodRevision` 是同一 `planId + startDate` 周期内递增修订号。
- `copiedFromVersionId` 只表示内容复制来源。
- `supersedesVersionId` 只在同周期修订确认时指向被替代版本。
- 确认时保存带 `schemaVersion` 的 ACTIVE 健康约束稳定 JSONB 快照，不直接序列化领域对象。
- 确认时在 `plan_version_goal` 保存目标摘要快照，历史版本展示不得受 Goal 后续修改影响。
- `confirm` 和 `cancel` 必须带 `expectedRevision`，并在状态转换前校验。
- 同一日期周期的新确认版本会替代旧 `CONFIRMED`；不同日期周期可同时为 `CONFIRMED`，但不得重叠。

### PlanDay

计划周期内的一天。

规则：

- 可确认草案必须恰好有 7 个 PlanDay。
- 日期必须连续、不重复且落在版本周期内。
- 标题必填。
- 休息日允许 0 个 PlanItem。

### PlanItem

计划日中的人工计划条目。

类型：

- `BODYWEIGHT`
- `GYM`
- `SWIMMING`
- `BASKETBALL`
- `RECOVERY`
- `REST`
- `CARDIO`
- `NUTRITION`
- `MEASUREMENT`
- `OTHER`

规则：

- 不建立复杂动作库。
- 数值字段不得为负数。
- RPE 存在时必须在 1 到 10。
- 可选关联 `Goal`，只能关联 `ACTIVE` 或 `PAUSED` 目标。

## 7. M2.5-A Agent 与设备模型

M2.5-A 不改变现有 `UserProfile`、`Goal`、`HealthConstraint`、`Plan` 和 `PlanVersion` 的业务语义，只新增技术与产品骨架模型。

### AppUser

单用户身份边界，用于后续设备和 AgentRun 归属。

字段：

- `id: UUID`
- `status: String`
- `createdAt: Instant`
- `updatedAt: Instant`

规则：

- 第一阶段只创建一个默认用户。
- 不实现注册、密码、找回密码、角色权限或多租户。

### Device

已登记设备。

字段：

- `id: UUID`
- `userId: UUID`
- `deviceName: String`
- `platform: DevicePlatform`
- `status: DeviceStatus`
- `trustLevel: DeviceTrustLevel`
- `createdAt: Instant`
- `updatedAt: Instant`
- `lastSeenAt: Instant?`
- `revokedAt: Instant?`

规则：

- 首台设备为 `TRUSTED_PRIMARY`。
- 后续设备通过 `PairingSession` 创建。
- 每台设备可单独撤销，撤销不影响其他设备。
- 不能撤销最后一台 `ACTIVE` 可信设备。
- `TRUSTED_PRIMARY` 必须先显式转移给另一台 `ACTIVE` 设备后才能撤销。

### BootstrapSession

首台设备初始化用的一次性 code 会话。

字段：

- `id: UUID`
- `codeHash: String`
- `status: BootstrapStatus`
- `expiresAt: Instant`
- `consumedAt: Instant?`
- `failureCount: Integer`
- `createdAt: Instant`
- `updatedAt: Instant`

规则：

- bootstrap code 只能由服务端 CLI 生成。
- 服务端只保存摘要，不保存明文。
- code 短时有效、一次性消费。
- 并发消费只能一个成功。
- 初始化完成后永久关闭首台初始化入口。

### PairingSession

后续设备配对会话。

字段：

- `id: UUID`
- `userId: UUID`
- `createdByDeviceId: UUID`
- `codeHash: String`
- `status: PairingStatus`
- `expiresAt: Instant`
- `consumedAt: Instant?`
- `cancelledAt: Instant?`
- `createdDeviceId: UUID?`
- `createdAt: Instant`
- `updatedAt: Instant`

规则：

- 只能由已授权设备创建。
- 一次性消费，过期或已消费后不能重放。
- 二维码或 payload 不携带长期访问令牌。
- 二维码 payload 只在创建响应中临时生成，不写入数据库、日志或审计。

### DeviceCredential

设备凭据摘要。

字段：

- `id: UUID`
- `deviceId: UUID`
- `accessTokenHash: String`
- `accessTokenExpiresAt: Instant`
- `refreshTokenHash: String`
- `refreshTokenExpiresAt: Instant`
- `revokedAt: Instant?`
- `createdAt: Instant`
- `updatedAt: Instant`

规则：

- access token 短期有效。
- refresh credential 长期、可轮换、可撤销。
- 服务端只保存摘要，不保存明文。

### CredentialResponseEnvelope

设备凭据类 POST 的幂等重放信封。

字段：

- `id: UUID`
- `operationType: String`
- `idempotencyKey: String`
- `requestHash: String`
- `encryptedResponse: String`
- `nonce: String`
- `encryptionKeyVersion: String`
- `expiresAt: Instant`
- `createdAt: Instant`

规则：

- 只用于 bootstrap 消费、配对消费和 token refresh 的成功响应重放。
- 使用 AES-GCM 保存加密响应体。
- 加密密钥由环境变量提供，不在仓库内配置明文默认值。
- 明文 access token、refresh credential 不进入普通幂等表、日志或审计。

### AgentRun

一次 Agent Runtime 技术运行，由 Java 作为权威系统创建、校验和保存。

字段：

- `id: UUID`
- `userId: UUID`
- `deviceId: UUID`
- `sessionId: UUID?`
- `triggerType: AgentTriggerType`
- `status: AgentRunStatus`
- `inputSummary: String`
- `structuredOutput: JSONB?`
- `validationResult: JSONB?`
- `failureCode: String?`
- `failureMessage: String?`
- `createdAt: Instant`
- `startedAt: Instant?`
- `completedAt: Instant?`
- `updatedAt: Instant`

状态：

- `CREATED`
- `RUNNING`
- `VALIDATING`
- `READY_FOR_USER_REVIEW`
- `FAILED`
- `CANCELLED`
- `EXPIRED`

规则：

- M2.5-A 不使用 `APPLIED`。
- Java 在创建事务提交后异步调用 Python Runtime，再对结构化结果做校验。
- 校验成功后进入 `READY_FOR_USER_REVIEW`。
- 失败时保存脱敏 `failureCode` 和 `failureMessage`。
- 关键 POST 使用幂等边界，重复请求不得创建重复运行或重复审计。

### AgentToolCall

Agent 工具调用可观测边界。M2.5-A 可没有真实业务工具调用，但保留运行审计结构。

字段：

- `id: UUID`
- `runId: UUID`
- `toolName: String`
- `permissionLevel: AgentToolPermissionLevel`
- `argumentSummary: String?`
- `resultSummary: String?`
- `status: AgentToolCallStatus`
- `latencyMs: Long?`
- `errorCode: String?`
- `createdAt: Instant`

## 8. 后续聚合占位

M3 以后再实现：

- `DailyExecution`
- `TrainingSession`
- `BodyMetricEntry`
- `SymptomEntry`
- `WeeklyAnalysis`
- `AdjustmentProposal`
- `AdjustmentDecision`

## 8. OPEN 未确认事项

- OPEN: `HealthConstraint.bodyRegion` 是否需要支持多选；M2A 默认单选。
- OPEN: 是否在 M2A API 中提供审计查询；默认只写入，不提供查询接口。
- OPEN: 是否将 `displayName` 默认填充为固定昵称；默认不自动填。
- OPEN: 是否在 M2A 前端显示 `RESOLVED` 项；默认在非归档列表中显示，并明确标记“已解决”。
