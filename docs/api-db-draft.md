# API 与数据库草案

本文档用于指导后续实现。M1 不创建业务迁移，不实现业务接口。

## 1. API 草案

### 档案与目标

```http
GET /api/v1/profile
PUT /api/v1/profile
GET /api/v1/health-constraints
POST /api/v1/health-constraints
PUT /api/v1/health-constraints/{id}
GET /api/v1/goals
POST /api/v1/goals
```

### 计划

```http
POST /api/v1/plans/draft-from-ai
GET /api/v1/plans/current
GET /api/v1/plans/{planId}/versions
GET /api/v1/plan-versions/{versionId}
POST /api/v1/plan-versions/{versionId}/activate
```

约束：

- `draft-from-ai` 只创建草案，不激活。
- `activate` 必须由用户操作触发。
- 一个计划同一时间只能有一个生效版本。

### 今日与执行

```http
GET /api/v1/today?date=YYYY-MM-DD
POST /api/v1/daily-logs
PATCH /api/v1/plan-items/{planItemId}/completion
POST /api/v1/training-sessions
POST /api/v1/body-metrics
POST /api/v1/symptoms
```

约束：

- 执行记录必须保存 `plan_version_id`。
- 历史记录不得随计划版本变化。

### 分析与调整

```http
POST /api/v1/analyses/weekly
GET /api/v1/analyses/{analysisId}
POST /api/v1/adjustment-proposals
GET /api/v1/adjustment-proposals/{proposalId}
POST /api/v1/adjustment-proposals/{proposalId}/decisions
GET /api/v1/audit-logs
```

约束：

- `adjustment-proposals` 必须经过 JSON Schema 校验。
- `decisions` 支持全部接受、部分接受、拒绝。
- 只有接受项能生成新计划版本。

## 2. 数据库核心表草案

### app_user_profile

个人档案。单人应用仍保留主键，方便外键和后续数据导出。

字段：

- `id`
- `sex`
- `birth_year`
- `height_cm`
- `notes`
- `created_at`
- `updated_at`

### health_constraint

健康约束和运动限制。

字段：

- `id`
- `profile_id`
- `constraint_type`
- `body_area`
- `severity`
- `description`
- `source`
- `active`
- `created_at`
- `updated_at`

约束：

- AI 不能删除或停用健康约束。

### goal

目标管理。

字段：

- `id`
- `profile_id`
- `goal_type`
- `target_value`
- `target_unit`
- `target_date`
- `status`
- `created_at`
- `updated_at`

### plan

计划主体。

字段：

- `id`
- `profile_id`
- `name`
- `status`
- `created_at`
- `updated_at`

### plan_version

计划版本。

字段：

- `id`
- `plan_id`
- `version_no`
- `status`
- `source`
- `created_from_version_id`
- `summary`
- `created_at`
- `activated_at`

约束：

- 同一 `plan_id` 只能有一个 `ACTIVE` 版本。
- `ACTIVE` 版本不可原地修改。

### plan_day

计划中的某一天。

字段：

- `id`
- `plan_version_id`
- `day_index`
- `planned_date`
- `focus`
- `notes`

### plan_item

计划任务。

字段：

- `id`
- `plan_day_id`
- `item_type`
- `title`
- `target_json`
- `safety_tags`
- `sort_order`

### daily_log

每日执行摘要。

字段：

- `id`
- `profile_id`
- `plan_version_id`
- `log_date`
- `sleep_minutes`
- `fatigue_score`
- `energy_score`
- `diet_adherence_score`
- `notes`
- `created_at`
- `updated_at`

约束：

- 同一 `profile_id` + `log_date` 只能有一条记录。

### body_metric_entry

身体指标记录。

字段：

- `id`
- `profile_id`
- `measured_at`
- `weight_kg`
- `waist_cm`
- `systolic_bp`
- `diastolic_bp`
- `resting_hr`
- `notes`

### symptom_entry

疼痛或不适记录。

字段：

- `id`
- `profile_id`
- `recorded_at`
- `body_area`
- `pain_score`
- `discomfort_score`
- `description`
- `trigger`

### training_session

训练记录。

字段：

- `id`
- `profile_id`
- `daily_log_id`
- `plan_item_id`
- `session_type`
- `started_at`
- `duration_minutes`
- `rpe`
- `pain_score`
- `details_json`
- `notes`

### training_set_record

力量训练组记录。

字段：

- `id`
- `training_session_id`
- `exercise_name`
- `set_index`
- `reps`
- `weight_kg`
- `duration_seconds`
- `distance_meters`
- `rpe`
- `pain_score`

### weekly_analysis

周期分析。

字段：

- `id`
- `profile_id`
- `plan_version_id`
- `period_start`
- `period_end`
- `summary_json`
- `created_at`

### rule_evaluation

规则评估结果。

字段：

- `id`
- `profile_id`
- `analysis_id`
- `rule_code`
- `decision`
- `severity`
- `evidence_json`
- `message`
- `created_at`

### adjustment_proposal

AI 调整建议。

字段：

- `id`
- `profile_id`
- `analysis_id`
- `plan_version_id`
- `schema_version`
- `status`
- `raw_response`
- `validated_json`
- `created_at`

### adjustment_proposal_item

建议项。

字段：

- `id`
- `proposal_id`
- `domain`
- `change_type`
- `target_ref`
- `before_json`
- `after_json`
- `rationale`
- `risks_json`
- `evidence_refs_json`
- `safety_rule_refs_json`
- `status`

### adjustment_decision

用户确认结果。

字段：

- `id`
- `proposal_id`
- `decision_type`
- `accepted_item_ids`
- `rejected_item_ids`
- `created_plan_version_id`
- `notes`
- `created_at`

### audit_log

审计记录。

字段：

- `id`
- `actor`
- `action`
- `entity_type`
- `entity_id`
- `before_json`
- `after_json`
- `created_at`

## 3. AI 建议 JSON 草案

```json
{
  "schemaVersion": "1.0",
  "period": {
    "start": "2026-07-01",
    "end": "2026-07-07"
  },
  "summary": "本周完成率偏低，建议降低复杂度并保持游泳适应训练。",
  "overallRiskLevel": "LOW",
  "items": [
    {
      "domain": "TRAINING",
      "changeType": "REDUCE_COMPLEXITY",
      "targetRef": {
        "type": "PLAN_ITEM",
        "id": "placeholder"
      },
      "before": {},
      "after": {},
      "rationale": "过去一周完成率不足，先降低复杂度。",
      "evidenceRefs": [],
      "risks": [],
      "safetyRuleRefs": []
    }
  ]
}
```

## 4. 规则引擎输出草案

```json
{
  "ruleCode": "SLEEP_LOW_BLOCK_VOLUME_INCREASE",
  "decision": "BLOCK",
  "severity": "HIGH",
  "message": "连续睡眠不足时禁止升级训练量。",
  "evidence": {
    "days": 3,
    "sleepMinutesAverage": 330
  },
  "blockedAdjustmentTypes": [
    "INCREASE_VOLUME",
    "INCREASE_INTENSITY"
  ]
}
```
