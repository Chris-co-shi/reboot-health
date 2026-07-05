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

个人档案聚合，保存单人应用的基础健康档案。

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

语义：

- 单人应用只允许一个当前档案。
- `baselineWeightKg` 只表示首次建立健康档案时的基线体重，可为空。
- 不保存 `currentWeightKg`。
- M3 后当前体重必须从最新 `BodyMetricEntry` 查询。
- 业务页面不得把 `baselineWeightKg` 展示为实时当前体重。

### HealthConstraint

健康约束聚合，表达高血压、颈椎、肩颈、髋、腰、足底、跟腱、禁止动作和训练注意事项等限制。

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

关键规则：

- AI 不能删除健康约束。
- AI 不能停用健康约束。
- M2A 允许用户手动创建、修改、停用和归档。
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

关键规则：

- 目标不是计划任务。
- 目标不直接包含每日训练动作。
- 已完成或已取消的目标不恢复为进行中；如需重新开始，应创建新目标。
- 归档不物理删除。

## 3. 枚举

`Sex`：

- `MALE`
- `FEMALE`
- `OTHER`
- `UNSPECIFIED`

`ConstraintType`：

- `HYPERTENSION`
- `CERVICAL_LIMITATION`
- `SHOULDER_NECK_DISCOMFORT`
- `LOWER_BACK_STRAIN`
- `HIP_MOBILITY_LIMITATION`
- `FOOT_SOLE_ISSUE`
- `ACHILLES_DISCOMFORT`
- `FORBIDDEN_MOVEMENT`
- `TRAINING_PRECAUTION`
- `OTHER`

`BodyRegion`：

- `CARDIOVASCULAR`
- `CERVICAL_SPINE`
- `SHOULDER_NECK`
- `LOWER_BACK`
- `HIP`
- `FOOT_SOLE`
- `ACHILLES_TENDON`
- `FULL_BODY`
- `OTHER`

`ConstraintSeverity`：

- `INFO`
- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

`ConstraintSourceType`：

- `USER_REPORTED`
- `DOCTOR_ADVICE`
- `MEDICAL_REPORT`
- `MEASUREMENT`
- `OTHER`

`ConstraintStatus`：

- `ACTIVE`
- `INACTIVE`
- `RESOLVED`
- `ARCHIVED`

`GoalType`：

- `WEIGHT`
- `WAIST`
- `TRAINING_HABIT`
- `AEROBIC_CAPACITY`
- `STRENGTH`
- `SWIMMING`
- `BASKETBALL_CONDITIONING`
- `SLEEP`
- `OTHER`

`GoalStatus`：

- `ACTIVE`
- `PAUSED`
- `COMPLETED`
- `CANCELLED`
- `ARCHIVED`

`GoalUnit`：

- `KG`
- `CM`
- `SESSIONS_PER_WEEK`
- `MINUTES`
- `MINUTES_PER_DAY`
- `METERS`
- `LAPS`
- `SCORE`
- `PERCENT`
- `NONE`

## 4. 状态流转

### HealthConstraint

| 当前状态 | 允许目标状态 |
|---|---|
| ACTIVE | INACTIVE, RESOLVED, ARCHIVED |
| INACTIVE | ACTIVE, RESOLVED, ARCHIVED |
| RESOLVED | ARCHIVED |
| ARCHIVED | 无 |

状态语义：

- `ACTIVE`：当前有效，必须进入后续规则引擎和 AI 当前上下文。
- `INACTIVE`：用户暂时停用，不参与规则判断；可作为历史信息进入 AI 上下文，但必须明确标记为非当前约束。
- `RESOLVED`：问题已解决或医生确认不再需要当前限制，不参与规则判断；M2A 不允许重新激活。
- `ARCHIVED`：用户主动归档，默认列表不显示，不参与规则和 AI 当前上下文，禁止普通编辑和状态变更，M2A 不实现恢复。

### Goal

| 当前状态 | 允许目标状态 |
|---|---|
| ACTIVE | PAUSED, COMPLETED, CANCELLED, ARCHIVED |
| PAUSED | ACTIVE, COMPLETED, CANCELLED, ARCHIVED |
| COMPLETED | ARCHIVED |
| CANCELLED | ARCHIVED |
| ARCHIVED | 无 |

状态语义：

- `ACTIVE`：正在执行。
- `PAUSED`：暂停执行，未来可以恢复。
- `COMPLETED`：已完成，终态。
- `CANCELLED`：已取消，终态。
- `ARCHIVED`：隐藏保留，终态。

## 5. 后续聚合占位

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

## 6. OPEN 未确认事项

- OPEN: `goalType = OTHER` 且 `unit = NONE` 时是否允许只填写文字目标说明。
- OPEN: `HealthConstraint.bodyRegion` 是否需要支持多选；M2A 默认单选。
- OPEN: 是否在 M2A API 中提供审计查询；默认只写入，不提供查询接口。
- OPEN: 是否将 `displayName` 默认填充为固定昵称；默认不自动填。
- OPEN: 是否在 M2A 前端显示 `RESOLVED` 项；默认在非归档列表中显示，并明确标记“已解决”。
