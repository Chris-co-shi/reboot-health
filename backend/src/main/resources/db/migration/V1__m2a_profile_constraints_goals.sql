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

CREATE INDEX idx_health_constraint_status ON health_constraint(status);
CREATE INDEX idx_health_constraint_type ON health_constraint(constraint_type);

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

CREATE INDEX idx_goal_status ON goal(status);
CREATE INDEX idx_goal_type ON goal(goal_type);

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

CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);
