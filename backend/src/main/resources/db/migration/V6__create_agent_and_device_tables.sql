CREATE TABLE app_user (
    id UUID PRIMARY KEY,
    singleton_key SMALLINT NOT NULL DEFAULT 1 CHECK (singleton_key = 1),
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uk_app_user_singleton UNIQUE (singleton_key),
    CONSTRAINT ck_app_user_status CHECK (status IN ('ACTIVE'))
);

CREATE TABLE bootstrap_session (
    id UUID PRIMARY KEY,
    code_hash CHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    failure_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_bootstrap_session_status
        CHECK (status IN ('CREATED', 'CONSUMED', 'EXPIRED', 'REVOKED')),
    CONSTRAINT ck_bootstrap_session_hash
        CHECK (code_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_bootstrap_session_failure_count
        CHECK (failure_count >= 0),
    CONSTRAINT ck_bootstrap_session_state_fields
        CHECK (
            (
                status = 'CREATED'
                AND consumed_at IS NULL
                AND revoked_at IS NULL
            )
            OR (
                status = 'CONSUMED'
                AND consumed_at IS NOT NULL
                AND revoked_at IS NULL
            )
            OR (
                status = 'EXPIRED'
                AND consumed_at IS NULL
                AND revoked_at IS NULL
            )
            OR (
                status = 'REVOKED'
                AND consumed_at IS NULL
                AND revoked_at IS NOT NULL
            )
        )
);

CREATE UNIQUE INDEX uk_bootstrap_session_active
    ON bootstrap_session ((1))
    WHERE status = 'CREATED';

CREATE TABLE device (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    device_name VARCHAR(100) NOT NULL,
    platform VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    trust_level VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_device_platform
        CHECK (platform IN ('IOS', 'ANDROID', 'MACOS', 'WINDOWS', 'UNKNOWN')),
    CONSTRAINT ck_device_status
        CHECK (status IN ('ACTIVE', 'REVOKED')),
    CONSTRAINT ck_device_trust_level
        CHECK (trust_level IN ('TRUSTED_PRIMARY', 'TRUSTED')),
    CONSTRAINT ck_device_revoked_fields
        CHECK (
            (status = 'REVOKED' AND revoked_at IS NOT NULL)
            OR (status = 'ACTIVE' AND revoked_at IS NULL)
        )
);

CREATE UNIQUE INDEX uk_device_primary
    ON device(user_id)
    WHERE trust_level = 'TRUSTED_PRIMARY';

CREATE TABLE device_credential (
    id UUID PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES device(id) ON DELETE RESTRICT,
    access_token_hash CHAR(64) NOT NULL,
    access_token_expires_at TIMESTAMPTZ NOT NULL,
    refresh_token_hash CHAR(64) NOT NULL,
    refresh_token_expires_at TIMESTAMPTZ NOT NULL,
    refresh_token_rotated_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uk_device_credential_device UNIQUE (device_id),
    CONSTRAINT uk_device_credential_access_hash UNIQUE (access_token_hash),
    CONSTRAINT uk_device_credential_refresh_hash UNIQUE (refresh_token_hash),
    CONSTRAINT ck_device_credential_access_hash
        CHECK (access_token_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_device_credential_refresh_hash
        CHECK (refresh_token_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_device_credential_expiry
        CHECK (refresh_token_expires_at > access_token_expires_at)
);

CREATE TABLE pairing_session (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    created_by_device_id UUID NOT NULL REFERENCES device(id) ON DELETE RESTRICT,
    code_hash CHAR(64) NOT NULL,
    qr_payload VARCHAR(1000) NOT NULL,
    status VARCHAR(32) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    created_device_id UUID REFERENCES device(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_pairing_session_status
        CHECK (status IN ('CREATED', 'CONSUMED', 'EXPIRED', 'CANCELLED')),
    CONSTRAINT ck_pairing_session_hash
        CHECK (code_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_pairing_session_state_fields
        CHECK (
            (
                status = 'CREATED'
                AND consumed_at IS NULL
                AND cancelled_at IS NULL
                AND created_device_id IS NULL
            )
            OR (
                status = 'CONSUMED'
                AND consumed_at IS NOT NULL
                AND cancelled_at IS NULL
                AND created_device_id IS NOT NULL
            )
            OR (
                status = 'EXPIRED'
                AND consumed_at IS NULL
                AND cancelled_at IS NULL
                AND created_device_id IS NULL
            )
            OR (
                status = 'CANCELLED'
                AND consumed_at IS NULL
                AND cancelled_at IS NOT NULL
                AND created_device_id IS NULL
            )
        )
);

CREATE INDEX idx_pairing_session_user_status ON pairing_session(user_id, status);
CREATE INDEX idx_device_user_status ON device(user_id, status);

CREATE TABLE agent_run (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE RESTRICT,
    device_id UUID NOT NULL REFERENCES device(id) ON DELETE RESTRICT,
    session_id UUID,
    trigger_type VARCHAR(64) NOT NULL,
    status VARCHAR(64) NOT NULL,
    input_summary VARCHAR(1000) NOT NULL,
    structured_output JSONB,
    validation_result JSONB,
    failure_code VARCHAR(64),
    failure_message VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_agent_run_trigger_type
        CHECK (trigger_type IN ('TECHNICAL_SMOKE_TEST')),
    CONSTRAINT ck_agent_run_status
        CHECK (status IN (
            'CREATED',
            'RUNNING',
            'VALIDATING',
            'READY_FOR_USER_REVIEW',
            'FAILED',
            'CANCELLED',
            'EXPIRED'
        )),
    CONSTRAINT ck_agent_run_completed_fields
        CHECK (
            (
                status IN ('READY_FOR_USER_REVIEW', 'FAILED', 'CANCELLED', 'EXPIRED')
                AND completed_at IS NOT NULL
            )
            OR (
                status IN ('CREATED', 'RUNNING', 'VALIDATING')
                AND completed_at IS NULL
            )
        ),
    CONSTRAINT ck_agent_run_success_fields
        CHECK (
            status <> 'READY_FOR_USER_REVIEW'
            OR (
                structured_output IS NOT NULL
                AND validation_result IS NOT NULL
                AND failure_code IS NULL
                AND failure_message IS NULL
            )
        ),
    CONSTRAINT ck_agent_run_failure_fields
        CHECK (
            status <> 'FAILED'
            OR (
                failure_code IS NOT NULL
                AND failure_message IS NOT NULL
            )
        )
);

CREATE TABLE agent_tool_call (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES agent_run(id) ON DELETE RESTRICT,
    tool_name VARCHAR(100) NOT NULL,
    permission_level VARCHAR(32) NOT NULL,
    argument_summary VARCHAR(1000),
    result_summary VARCHAR(1000),
    status VARCHAR(32) NOT NULL,
    latency_ms INTEGER,
    error_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_agent_tool_call_permission
        CHECK (permission_level IN ('READ', 'PROPOSE', 'COMMAND', 'SAFETY')),
    CONSTRAINT ck_agent_tool_call_status
        CHECK (status IN ('STARTED', 'SUCCEEDED', 'FAILED')),
    CONSTRAINT ck_agent_tool_call_latency
        CHECK (latency_ms IS NULL OR latency_ms >= 0)
);

CREATE INDEX idx_agent_run_user_status ON agent_run(user_id, status);
CREATE INDEX idx_agent_tool_call_run ON agent_tool_call(run_id);
