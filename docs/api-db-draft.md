# API 与数据库草案

本文档随里程碑持续更新。当前实现目标为 M2A：用户档案、健康约束、目标管理。

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
- 归档必须提供 `archiveReason`。
- 已归档约束禁止普通编辑和状态变更。
- Repository 不提供业务语义的 `archive` 方法；应用服务完成状态变化后调用 `save`。

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
- 已完成或已取消的目标如需重新开始，应创建新目标。
- 已归档目标禁止普通编辑和状态变更。

## 2. M2A 数据库表

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

审计表只追加，不提供更新和删除业务接口。

## 3. DTO 校验

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
- `targetValue`、`baselineValue` 必须 `>= 0`。
- `targetDate` 可选。
- `priority`：1-5。
- `WEIGHT` 默认使用 `KG`。
- `WAIST` 默认使用 `CM`。
- `TRAINING_HABIT` 默认使用 `SESSIONS_PER_WEEK`。
- `SWIMMING` 可使用 `METERS` 或 `LAPS`。
- `SLEEP` 可使用 `MINUTES` 或 `MINUTES_PER_DAY`。
- `unit = NONE` 时，`targetValue` 和 `baselineValue` 应为空。
- 不合法组合返回 `GOAL_INVALID_TARGET`。
- 不自动修正单位。

## 4. 错误码

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
- `ENUM_INVALID`
- `VALIDATION_ERROR`
- `DATA_CONFLICT`
- `AUDIT_WRITE_FAILED`

## 5. 后续 API 占位

M2A 不实现以下 API：

- 计划和计划版本。
- 今日执行。
- 训练记录。
- 身体指标和症状。
- 周分析。
- AI 调整建议。
