ALTER TABLE plan_item
    DROP CONSTRAINT ck_plan_item_type;

ALTER TABLE plan_item
    ADD CONSTRAINT ck_plan_item_type
        CHECK (
            item_type IN (
                'BODYWEIGHT',
                'GYM',
                'SWIMMING',
                'BASKETBALL',
                'RECOVERY',
                'REST',
                'CARDIO',
                'NUTRITION',
                'MEASUREMENT',
                'OTHER'
            )
        );

ALTER TABLE plan_version_goal
    ADD COLUMN goal_title VARCHAR(100),
    ADD COLUMN goal_type VARCHAR(64),
    ADD COLUMN goal_status VARCHAR(32),
    ADD COLUMN target_value NUMERIC(12,3),
    ADD COLUMN unit VARCHAR(32),
    ADD COLUMN baseline_value NUMERIC(12,3),
    ADD COLUMN target_date DATE;

ALTER TABLE plan_version
    ADD CONSTRAINT ck_plan_version_v5_status_timestamps
        CHECK (
            (
                status = 'DRAFT'
                AND confirmed_at IS NULL
                AND superseded_at IS NULL
                AND cancelled_at IS NULL
                AND cancel_reason IS NULL
                AND supersedes_version_id IS NULL
                AND health_constraint_snapshot IS NULL
            )
            OR (
                status = 'CONFIRMED'
                AND confirmed_at IS NOT NULL
                AND superseded_at IS NULL
                AND cancelled_at IS NULL
                AND cancel_reason IS NULL
                AND health_constraint_snapshot IS NOT NULL
            )
            OR (
                status = 'SUPERSEDED'
                AND confirmed_at IS NOT NULL
                AND superseded_at IS NOT NULL
                AND cancelled_at IS NULL
                AND cancel_reason IS NULL
                AND health_constraint_snapshot IS NOT NULL
            )
            OR (
                status = 'CANCELLED'
                AND confirmed_at IS NULL
                AND superseded_at IS NULL
                AND cancelled_at IS NOT NULL
                AND cancel_reason IS NOT NULL
                AND btrim(cancel_reason) <> ''
                AND health_constraint_snapshot IS NULL
            )
        );

ALTER TABLE idempotency_record
    ADD CONSTRAINT ck_idempotency_record_v5_key_and_hash
        CHECK (
            btrim(idempotency_key) <> ''
            AND btrim(operation_code) <> ''
            AND request_hash ~ '^[0-9a-f]{64}$'
        ),
    ADD CONSTRAINT ck_idempotency_record_v5_state_fields
        CHECK (
            (
                state = 'PROCESSING'
                AND resource_type IS NULL
                AND resource_id IS NULL
                AND response_status IS NULL
                AND completed_at IS NULL
            )
            OR (
                state = 'COMPLETED'
                AND resource_type IS NOT NULL
                AND resource_id IS NOT NULL
                AND response_status IS NOT NULL
                AND completed_at IS NOT NULL
            )
        );
