# 领域模型

## 1. 建模原则

- 先保证计划闭环和安全不变量，再扩展训练内容库。
- 计划、执行、分析、AI 建议、用户确认必须分离。
- 历史执行记录是事实，不能随计划版本变化。
- AI 输出是建议，不是领域事实。
- 医疗相关内容只作为约束、提醒和风险信息，不生成诊断结论。

## 2. 核心聚合

### UserProfile

个人档案聚合，保存用户基础信息和当前健康管理上下文。

职责：

- 保存基础档案。
- 关联健康约束。
- 关联目标。

不负责：

- 不直接生成计划。
- 不执行训练调整。

### HealthConstraint

健康约束聚合，表达高血压、颈椎、肩颈、髋、腰、足底、跟腱等限制。

职责：

- 作为规则引擎和 AI 上下文的强约束输入。
- 记录约束来源、严重程度、状态。

关键规则：

- AI 不能删除健康约束。
- AI 不能停用健康约束。

### Goal

目标聚合，表达体重、体能、训练习惯等目标。

职责：

- 保存目标值、目标类型、状态。
- 为计划生成和周分析提供方向。

### Plan

计划主体聚合，承载一组计划版本。

职责：

- 组织计划版本。
- 保证同一计划只有一个生效版本。

### PlanVersion

计划版本聚合，是计划变更的核心边界。

职责：

- 保存某一版一周计划。
- 表达草案、生效、归档等状态。
- 记录来源：用户创建、AI 起草、用户确认 AI 调整。

关键规则：

- 生效版本不可原地修改。
- 调整必须创建新版本。
- 新版本必须保留来源版本。

### DailyExecution

每日执行聚合，记录某一天对当时计划版本的执行事实。

职责：

- 保存每日计划完成情况。
- 汇总睡眠、疲劳、精力、饮食执行等日级状态。
- 关联训练记录和身体指标。

关键规则：

- 必须引用当时的 `plan_version_id`。
- 不随新计划版本变化。

### TrainingSession

训练记录聚合，记录徒手、健身房、游泳、篮球等训练事实。

职责：

- 保存训练类型、时长、RPE、疼痛评分。
- 保存项目特有详情。

### BodyMetricEntry

身体指标记录聚合。

职责：

- 记录体重、腰围、血压、静息心率。
- 支持趋势分析。

### SymptomEntry

症状和主观不适记录聚合。

职责：

- 记录部位、疼痛评分、不适评分、触发因素和备注。
- 为安全规则提供依据。

### WeeklyAnalysis

周期分析聚合。

职责：

- 保存 7 天周期统计快照。
- 汇总完成率、体重、血压、睡眠、疲劳、疼痛、训练负荷。
- 作为 AI 调整建议的输入之一。

### AdjustmentProposal

AI 调整建议聚合。

职责：

- 保存 AI 原始响应。
- 保存 JSON Schema 校验后的结构化建议。
- 记录规则校验结果。

关键规则：

- 未通过 Schema 校验不得进入领域应用流程。
- 被规则阻断的建议项不可应用。

### AdjustmentDecision

用户确认聚合。

职责：

- 记录全部接受、部分接受或拒绝。
- 记录接受项和拒绝项。
- 关联新生成的计划版本。

### AuditLog

审计记录聚合。

职责：

- 记录关键状态转换。
- 记录调整前后差异。
- 支持回溯计划版本变化原因。

## 3. 领域事件草案

- `PlanDraftCreated`
- `PlanVersionActivated`
- `DailyLogSubmitted`
- `WeeklyAnalysisGenerated`
- `AdjustmentProposalCreated`
- `AdjustmentProposalValidated`
- `AdjustmentDecisionSubmitted`
- `PlanVersionCreatedFromAdjustment`
- `SafetyRuleBlockedAdjustment`

## 4. 聚合关系

```text
UserProfile
  -> HealthConstraint
  -> Goal
  -> Plan
       -> PlanVersion
            -> PlanDay
                 -> PlanItem

PlanVersion
  -> DailyExecution
       -> TrainingSession
       -> BodyMetricEntry
       -> SymptomEntry

WeeklyAnalysis
  -> RuleEvaluation
  -> AdjustmentProposal
       -> AdjustmentProposalItem
       -> AdjustmentDecision
            -> PlanVersion
```

## 5. 状态流转

计划版本：

```text
DRAFT -> ACTIVE -> ARCHIVED
DRAFT -> REJECTED
```

调整建议：

```text
CREATED -> SCHEMA_VALIDATED -> RULE_CHECKED -> PENDING_USER_DECISION
PENDING_USER_DECISION -> ACCEPTED
PENDING_USER_DECISION -> PARTIALLY_ACCEPTED
PENDING_USER_DECISION -> REJECTED
```

规则结果：

```text
ALLOW
WARN
BLOCK
```

## 6. OPEN 未确认事项

- OPEN: 计划版本是否只支持 7 天周期，还是数据库层预留更长周期字段。
- OPEN: 训练动作是否在 MVP 阶段建立动作字典，还是仅保存自由文本。
- OPEN: 疼痛部位枚举是否先固定，还是允许用户自定义。
- OPEN: 周分析是否允许用户手动触发重算。
- OPEN: 审计记录保留策略是否永久保留。
