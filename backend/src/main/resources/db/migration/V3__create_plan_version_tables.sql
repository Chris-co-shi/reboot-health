CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE plan (
    id UUID PRIMARY KEY,
    singleton_key SMALLINT NOT NULL DEFAULT 1 CHECK (singleton_key = 1),
    title VARCHAR(100) NOT NULL,
    summary VARCHAR(1000),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uk_plan_singleton UNIQUE (singleton_key)
);

CREATE TABLE plan_version (
    id UUID PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES plan(id) ON DELETE RESTRICT,
    version_number INTEGER NOT NULL,
    period_revision INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    title VARCHAR(100) NOT NULL,
    summary VARCHAR(1000),
    copied_from_version_id UUID REFERENCES plan_version(id) ON DELETE RESTRICT,
    supersedes_version_id UUID REFERENCES plan_version(id) ON DELETE RESTRICT,
    health_constraint_snapshot JSONB,
    revision INTEGER NOT NULL,
    confirmed_at TIMESTAMPTZ,
    superseded_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancel_reason VARCHAR(300),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT ck_plan_version_status
        CHECK (status IN ('DRAFT', 'CONFIRMED', 'SUPERSEDED', 'CANCELLED')),
    CONSTRAINT ck_plan_version_period
        CHECK (end_date = start_date + 6),
    CONSTRAINT ck_plan_version_revision
        CHECK (revision >= 0),
    CONSTRAINT ck_plan_version_numbers
        CHECK (version_number >= 1 AND period_revision >= 0),
    CONSTRAINT ck_plan_version_confirmed_fields
        CHECK (
            (status = 'CONFIRMED' AND confirmed_at IS NOT NULL AND cancelled_at IS NULL)
            OR status <> 'CONFIRMED'
        ),
    CONSTRAINT ck_plan_version_superseded_fields
        CHECK (
            (status = 'SUPERSEDED' AND superseded_at IS NOT NULL)
            OR status <> 'SUPERSEDED'
        ),
    CONSTRAINT ck_plan_version_cancelled_fields
        CHECK (
            (
                status = 'CANCELLED'
                AND cancelled_at IS NOT NULL
                AND cancel_reason IS NOT NULL
                AND btrim(cancel_reason) <> ''
            )
            OR (
                status <> 'CANCELLED'
                AND cancelled_at IS NULL
                AND cancel_reason IS NULL
            )
        ),
    CONSTRAINT uk_plan_version_number UNIQUE (plan_id, version_number),
    CONSTRAINT uk_plan_version_period_revision UNIQUE (plan_id, start_date, period_revision),
    CONSTRAINT ex_plan_version_confirmed_period
        EXCLUDE USING gist (
            plan_id WITH =,
            daterange(start_date, end_date, '[]') WITH &&
        )
        WHERE (status = 'CONFIRMED')
);

CREATE UNIQUE INDEX uk_plan_version_draft_period
    ON plan_version(plan_id, start_date)
    WHERE status = 'DRAFT';

CREATE UNIQUE INDEX uk_plan_version_confirmed_period
    ON plan_version(plan_id, start_date)
    WHERE status = 'CONFIRMED';

CREATE INDEX idx_plan_version_status_period ON plan_version(status, start_date, end_date);
CREATE INDEX idx_plan_version_plan ON plan_version(plan_id);

CREATE TABLE plan_day (
    id UUID PRIMARY KEY,
    version_id UUID NOT NULL REFERENCES plan_version(id) ON DELETE RESTRICT,
    day_date DATE NOT NULL,
    title VARCHAR(100) NOT NULL,
    note VARCHAR(1000),
    sort_order INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uk_plan_day_version_date UNIQUE (version_id, day_date),
    CONSTRAINT uk_plan_day_version_order UNIQUE (version_id, sort_order),
    CONSTRAINT ck_plan_day_sort_order CHECK (sort_order BETWEEN 1 AND 7)
);

CREATE TABLE plan_item (
    id UUID PRIMARY KEY,
    day_id UUID NOT NULL REFERENCES plan_day(id) ON DELETE RESTRICT,
    goal_id UUID REFERENCES goal(id) ON DELETE RESTRICT,
    item_type VARCHAR(64) NOT NULL,
    title VARCHAR(100) NOT NULL,
    description VARCHAR(1000),
    planned_sets NUMERIC(8,2),
    planned_reps NUMERIC(8,2),
    planned_duration_minutes NUMERIC(8,2),
    planned_distance_meters NUMERIC(10,2),
    planned_rpe NUMERIC(4,1),
    sort_order INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uk_plan_item_day_order UNIQUE (day_id, sort_order),
    CONSTRAINT ck_plan_item_type
        CHECK (item_type IN ('BODYWEIGHT', 'GYM', 'SWIMMING', 'BASKETBALL', 'RECOVERY', 'REST', 'OTHER')),
    CONSTRAINT ck_plan_item_values
        CHECK (
            (planned_sets IS NULL OR planned_sets >= 0)
            AND (planned_reps IS NULL OR planned_reps >= 0)
            AND (planned_duration_minutes IS NULL OR planned_duration_minutes >= 0)
            AND (planned_distance_meters IS NULL OR planned_distance_meters >= 0)
            AND (planned_rpe IS NULL OR planned_rpe BETWEEN 1 AND 10)
            AND sort_order >= 1
        )
);

CREATE TABLE plan_version_goal (
    version_id UUID NOT NULL REFERENCES plan_version(id) ON DELETE RESTRICT,
    goal_id UUID NOT NULL REFERENCES goal(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (version_id, goal_id)
);

CREATE OR REPLACE FUNCTION validate_plan_day_in_period()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    period_start DATE;
    period_end DATE;
BEGIN
    SELECT start_date, end_date
    INTO period_start, period_end
    FROM plan_version
    WHERE id = NEW.version_id;

    IF period_start IS NULL THEN
        RAISE EXCEPTION 'plan_day references missing plan_version: %', NEW.version_id;
    END IF;

    IF NEW.day_date < period_start OR NEW.day_date > period_end THEN
        RAISE EXCEPTION 'plan_day date out of version period: %', NEW.day_date;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_plan_day_in_period
BEFORE INSERT OR UPDATE ON plan_day
FOR EACH ROW
EXECUTE FUNCTION validate_plan_day_in_period();

CREATE INDEX idx_plan_day_version ON plan_day(version_id);
CREATE INDEX idx_plan_item_day ON plan_item(day_id);
CREATE INDEX idx_plan_item_goal ON plan_item(goal_id);
CREATE INDEX idx_plan_version_goal_goal ON plan_version_goal(goal_id);
