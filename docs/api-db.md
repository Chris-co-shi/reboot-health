# API 与数据库

本文档记录当前已实现或本轮修复中的 API 与数据库结构。未实现内容必须明确标记。

## 1. M2A REST API

### UserProfile

```http
GET /api/v1/profile
PUT /api/v1/profile
```

规则：

- 单人应用只保存一个当前档案。
- `GET` 未初始化时返回 `PROFILE_NOT_INITIALIZED`。
- `PUT` 首次保存时创建档案，之后更新同一条档案。
- 请求内容与当前数据完全一致时视为幂等无变化，不重复写业务记录，不写 `NO_CHANGE` 审计。

### HealthConstraint

```http
GET /api/v1/health-constraints?status=&includeArchived=false
POST /api/v1/health-constraints
PUT /api/v1/health-constraints/{id}
PATCH /api/v1/health-constraints/{id}/status
POST /api/v1/health-constraints/{id}/archive
```

规则：

- 默认不返回 `ARCHIVED`。
- 普通状态接口不得把状态改为 `ARCHIVED`。
- 归档必须走专用 archive 接口并提供 `archiveReason`。
- 已归档约束禁止普通编辑和状态变更。

### Goal

```http
GET /api/v1/goals?status=&includeArchived=false
POST /api/v1/goals
PUT /api/v1/goals/{id}
PATCH /api/v1/goals/{id}/status
POST /api/v1/goals/{id}/archive
```

规则：

- 默认不返回 `ARCHIVED`。
- `targetDate` 可选。
- 普通状态接口不得把状态改为 `ARCHIVED`。
- 只有 `ACTIVE` 和 `PAUSED` 目标允许 PUT 修改内容。
- 已完成或已取消的目标如需重新开始，应创建新目标。

## 2. 数据库表

所有时间戳由应用统一产生。Java 类型映射：

- `DATE -> LocalDate`
- `TIMESTAMPTZ -> Instant`

禁止使用 `LocalDateTime` 表达审计时间。

### app_user_profile

```sql
CREATE TABLE app_user_profile (
    id UUID PRIMARY KEY,
    singleton_key SMALLINT NOT NULL DEFAULT 1 CHECK (singleton_key = 1),
    display_name VARCHAR(60) NOT NULL,
    sex VARCHAR(32) NOT NULL,
    birth_date DATE,
    height_cm NUMERIC(5,2),
    baseline_weight_kg NUMERIC(6,2),
    timezone VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uk_app_user_profile_singleton UNIQUE (singleton_key)
);
```

### health_constraint

```sql
CREATE TABLE health_constraint (
    id UUID PRIMARY KEY,
    constraint_type VARCHAR(64) NOT NULL,
    body_region VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    source_type VARCHAR(64) NOT NULL,
    source_note VARCHAR(1000),
    status VARCHAR(32) NOT NULL,
    effective_from DATE,
    effective_to DATE,
    archive_reason VARCHAR(300),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    archived_at TIMESTAMPTZ,
    CONSTRAINT ck_health_constraint_effective_range
        CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from)
);
```

V2 增强约束：

- 归档状态必须有 `archive_reason` 和 `archived_at`。
- 非归档状态不得有 `archive_reason` 或 `archived_at`。

### goal

```sql
CREATE TABLE goal (
    id UUID PRIMARY KEY,
    goal_type VARCHAR(64) NOT NULL,
    title VARCHAR(100) NOT NULL,
    target_value NUMERIC(12,3),
    unit VARCHAR(32) NOT NULL,
    baseline_value NUMERIC(12,3),
    target_date DATE,
    status VARCHAR(32) NOT NULL,
    priority INTEGER NOT NULL,
    archive_reason VARCHAR(300),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    archived_at TIMESTAMPTZ
);
```

V2 增强约束：

- `priority BETWEEN 1 AND 5`。
- `target_value IS NULL OR target_value >= 0`。
- `baseline_value IS NULL OR baseline_value >= 0`。
- 归档状态必须有 `archive_reason` 和 `archived_at`。
- 非归档状态不得有 `archive_reason` 或 `archived_at`。

### audit_log

```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY,
    actor VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id UUID NOT NULL,
    before_snapshot JSONB,
    after_snapshot JSONB,
    created_at TIMESTAMPTZ NOT NULL
);
```

审计表只追加，不提供更新和删除业务接口。JSONB 写入保留专用 SQL 显式 `CAST(... AS jsonb)`。

## 3. Repository 持久化语义

- `UserProfileRepository`：`findCurrent`、`insert`、`update`。
- `HealthConstraintRepository`：`findById`、`findAll`、`insert`、`update`。
- `GoalRepository`：`findById`、`findAll`、`insert`、`update`。
- `AuditLogRepository`：`append`。

`insert` 使用 `BaseMapper.insert`，`update` 使用 `BaseMapper.updateById`。不得通过保存前查询模拟泛化 `save`。

## 4. DTO 校验

UserProfile：

- `displayName`：1-60。
- `birthDate`：不得晚于今天。
- `heightCm`：100-250，可为空。
- `baselineWeightKg`：30-300，可为空。
- `timezone`：合法 IANA 时区。

HealthConstraint：

- `title`：1-100。
- `description`：最长 2000。
- `sourceNote`：最长 1000。
- `archiveReason`：归档时必填，1-300。
- `effectiveTo` 不早于 `effectiveFrom`。
- 枚举值必须合法。

Goal：

- `title`：1-100。
- `targetDate` 可选。
- `priority`：1-5。
- 除 `OTHER + NONE` 外，`targetValue` 必填且必须 `>= 0`。
- `baselineValue` 可为空；存在时必须 `>= 0`。
- `unit` 和 `goalType` 必须匹配。
- `OTHER + NONE` 时 `targetValue` 和 `baselineValue` 必须为空。
- 不合法组合返回 `GOAL_INVALID_TARGET`。
- 不自动修正单位。

## 5. 错误码

- `PROFILE_NOT_INITIALIZED`
- `PROFILE_VALIDATION_FAILED`
- `HEALTH_CONSTRAINT_NOT_FOUND`
- `HEALTH_CONSTRAINT_ARCHIVED`
- `HEALTH_CONSTRAINT_INVALID_STATUS_TRANSITION`
- `HEALTH_CONSTRAINT_INVALID_DATE_RANGE`
- `GOAL_NOT_FOUND`
- `GOAL_ARCHIVED`
- `GOAL_INVALID_STATUS_TRANSITION`
- `GOAL_INVALID_TARGET`
- `IDEMPOTENCY_KEY_REQUIRED`
- `IDEMPOTENCY_KEY_INVALID`
- `IDEMPOTENCY_KEY_REUSED`
- `PLAN_NOT_FOUND`
- `PLAN_ALREADY_EXISTS`
- `PLAN_CURRENT_NOT_FOUND`
- `PLAN_VERSION_NOT_FOUND`
- `PLAN_VERSION_NOT_DRAFT`
- `PLAN_VERSION_IMMUTABLE`
- `PLAN_VERSION_INVALID_PERIOD`
- `PLAN_VERSION_INCOMPLETE`
- `PLAN_VERSION_REVISION_CONFLICT`
- `PLAN_VERSION_PERIOD_OVERLAP`
- `PLAN_VERSION_SOURCE_INVALID`
- `PLAN_DAY_NOT_FOUND`
- `PLAN_DAY_DATE_OUT_OF_RANGE`
- `PLAN_ITEM_NOT_FOUND`
- `PLAN_ITEM_INVALID_VALUE`
- `ENUM_INVALID`
- `VALIDATION_ERROR`
- `DATA_CONFLICT`
- `AUDIT_WRITE_FAILED`
- `INTERNAL_ERROR`

## 6. M2B REST API

必须带 `Idempotency-Key` 的 POST：

- `POST /api/v1/plans`
- `POST /api/v1/plans/{planId}/versions`
- `POST /api/v1/plan-versions/{sourceVersionId}/copy`
- `POST /api/v1/plan-versions/{versionId}/confirm`
- `POST /api/v1/plan-versions/{versionId}/cancel`
- `POST /api/v1/plan-versions/{versionId}/days`
- `POST /api/v1/plan-days/{dayId}/items`

Plan：

```http
GET /api/v1/plans
POST /api/v1/plans
GET /api/v1/plans/current
GET /api/v1/plans/{planId}
GET /api/v1/plans/{planId}/versions?status=
POST /api/v1/plans/{planId}/versions
```

`GET /api/v1/plans/current` 按 `UserProfile.timezone` 计算当前日期；档案不存在时使用 `app.default-timezone`，不使用 JVM 默认时区。

PlanVersion：

```http
GET /api/v1/plan-versions/{versionId}
GET /api/v1/plan-versions/{versionId}/preview
PUT /api/v1/plan-versions/{versionId}
POST /api/v1/plan-versions/{versionId}/confirm
POST /api/v1/plan-versions/{versionId}/cancel
POST /api/v1/plan-versions/{sourceVersionId}/copy
```

`confirm` 请求体：

```json
{
  "expectedRevision": 0
}
```

`cancel` 请求体：

```json
{
  "cancelReason": "人工取消原因",
  "expectedRevision": 0
}
```

`preview` 返回独立预览响应，至少包含 `detail`、`goals`、`healthConstraints`、`validationIssues`、`canConfirm`。其中已确认历史版本的 `goals` 和 `healthConstraints` 必须来自确认时快照。

PlanDay / PlanItem：

```http
POST /api/v1/plan-versions/{versionId}/days
PUT /api/v1/plan-days/{dayId}
DELETE /api/v1/plan-days/{dayId}?expectedRevision=
POST /api/v1/plan-days/{dayId}/items
PUT /api/v1/plan-items/{itemId}
DELETE /api/v1/plan-items/{itemId}?expectedRevision=
```

DELETE 不要求 `Idempotency-Key`，但删除前必须校验版本仍为 `DRAFT` 且 `expectedRevision` 匹配。stale revision 返回 `PLAN_VERSION_REVISION_CONFLICT`。

幂等规则：

- 相同 key、相同 operation、相同规范化 command hash 返回第一次资源结果。
- 幂等重放不重新执行业务，不重新写审计。
- 相同 key 但 operation 或请求内容不同返回 `IDEMPOTENCY_KEY_REUSED`。
- 幂等记录、业务修改和审计处于同一事务。
- `confirm` 和 `cancel` 的 `requestHash` 包含 `expectedRevision`。
- 网络错误、408、429 和 5xx 后前端重试必须复用原 `Idempotency-Key`；只有明确 4xx 业务失败才清除 key。

## 7. M2B 数据库表

新增 Flyway：

- `V3__create_plan_version_tables.sql`
- `V4__create_idempotency_record.sql`
- `V5__strengthen_m2b_integrity.sql`

核心表：

- `plan`：唯一长期计划身份。
- `plan_version`：7 天计划版本，含 `DRAFT`、`CONFIRMED`、`SUPERSEDED`、`CANCELLED`。
- `plan_day`：版本内 7 天。
- `plan_item`：计划日条目。
- `plan_version_goal`：版本与目标关联；V5 起保存确认时目标摘要快照。
- `idempotency_record`：POST 幂等记录。

关键约束：

- `plan.singleton_key` 保证单人应用只有一个长期 Plan。
- `plan_version.end_date = start_date + 6`。
- 同一 `plan_id + start_date` 只允许一个 `DRAFT`。
- 同一 `plan_id + start_date` 只允许一个 `CONFIRMED`。
- PostgreSQL exclusion constraint 禁止重叠 `CONFIRMED` 周期。
- `plan_day` 日期由 trigger 保证落在版本周期内。
- `idempotency_record.idempotency_key` 全局唯一。
- `idempotency_record.state` 只允许 `PROCESSING`、`COMPLETED`。
- V5 扩展 `plan_item.item_type`：`CARDIO`、`NUTRITION`、`MEASUREMENT`。
- V5 增加 `plan_version` 状态与时间字段、取消原因、健康约束快照的一致性约束。
- V5 增加 `idempotency_record` 的 PROCESSING/COMPLETED 字段完整性约束。
- 重叠 `CONFIRMED` 周期必须返回 `PLAN_VERSION_PERIOD_OVERLAP`，不返回通用 `DATA_CONFLICT`。

## 8. 后续 API 占位

M2B 不实现以下 API：

- 今日执行。
- 训练记录。
- 身体指标和症状。
- 周分析。
- AI 调整建议。
