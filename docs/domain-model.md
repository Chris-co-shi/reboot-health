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

## 6. 后续聚合占位

M2B 以后再实现：

- `Plan`
- `PlanVersion`
- `PlanDay`
- `PlanItem`
- `DailyExecution`
- `TrainingSession`
- `BodyMetricEntry`
- `SymptomEntry`
- `WeeklyAnalysis`
- `AdjustmentProposal`
- `AdjustmentDecision`

## 7. OPEN 未确认事项

- OPEN: `HealthConstraint.bodyRegion` 是否需要支持多选；M2A 默认单选。
- OPEN: 是否在 M2A API 中提供审计查询；默认只写入，不提供查询接口。
- OPEN: 是否将 `displayName` 默认填充为固定昵称；默认不自动填。
- OPEN: 是否在 M2A 前端显示 `RESOLVED` 项；默认在非归档列表中显示，并明确标记“已解决”。
