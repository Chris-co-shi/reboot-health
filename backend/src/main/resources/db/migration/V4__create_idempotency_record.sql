CREATE TABLE idempotency_record (
    id UUID PRIMARY KEY,
    idempotency_key VARCHAR(128) NOT NULL,
    operation_code VARCHAR(64) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    state VARCHAR(16) NOT NULL,
    resource_type VARCHAR(64),
    resource_id UUID,
    response_status SMALLINT,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    CONSTRAINT uk_idempotency_record_key UNIQUE (idempotency_key),
    CONSTRAINT ck_idempotency_record_state
        CHECK (state IN ('PROCESSING', 'COMPLETED')),
    CONSTRAINT ck_idempotency_record_completed_fields
        CHECK (
            (
                state = 'COMPLETED'
                AND resource_type IS NOT NULL
                AND resource_id IS NOT NULL
                AND response_status IS NOT NULL
                AND completed_at IS NOT NULL
            )
            OR (
                state = 'PROCESSING'
                AND completed_at IS NULL
            )
        )
);

CREATE INDEX idx_idempotency_record_resource ON idempotency_record(resource_type, resource_id);
