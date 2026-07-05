-- V2 先检查已有数据，再增加约束。
-- 不自动伪造归档原因、归档时间或审计记录；发现不一致数据时让 Flyway 失败并给出表名和问题类型。
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM health_constraint
        WHERE status = 'ARCHIVED' AND archived_at IS NULL
    ) THEN
        RAISE EXCEPTION 'M2A data check failed: health_constraint ARCHIVED rows must have archived_at';
    END IF;

    IF EXISTS (
        SELECT 1 FROM health_constraint
        WHERE status = 'ARCHIVED' AND (archive_reason IS NULL OR btrim(archive_reason) = '')
    ) THEN
        RAISE EXCEPTION 'M2A data check failed: health_constraint ARCHIVED rows must have archive_reason';
    END IF;

    IF EXISTS (
        SELECT 1 FROM health_constraint
        WHERE status <> 'ARCHIVED' AND (archived_at IS NOT NULL OR archive_reason IS NOT NULL)
    ) THEN
        RAISE EXCEPTION 'M2A data check failed: health_constraint non-ARCHIVED rows must not have archive fields';
    END IF;

    IF EXISTS (
        SELECT 1 FROM goal
        WHERE status = 'ARCHIVED' AND archived_at IS NULL
    ) THEN
        RAISE EXCEPTION 'M2A data check failed: goal ARCHIVED rows must have archived_at';
    END IF;

    IF EXISTS (
        SELECT 1 FROM goal
        WHERE status = 'ARCHIVED' AND (archive_reason IS NULL OR btrim(archive_reason) = '')
    ) THEN
        RAISE EXCEPTION 'M2A data check failed: goal ARCHIVED rows must have archive_reason';
    END IF;

    IF EXISTS (
        SELECT 1 FROM goal
        WHERE status <> 'ARCHIVED' AND (archived_at IS NOT NULL OR archive_reason IS NOT NULL)
    ) THEN
        RAISE EXCEPTION 'M2A data check failed: goal non-ARCHIVED rows must not have archive fields';
    END IF;
END $$;

ALTER TABLE health_constraint
    ADD CONSTRAINT ck_health_constraint_archive_fields
        CHECK (
            (
                status = 'ARCHIVED'
                AND archived_at IS NOT NULL
                AND archive_reason IS NOT NULL
                AND btrim(archive_reason) <> ''
            )
            OR (
                status <> 'ARCHIVED'
                AND archived_at IS NULL
                AND archive_reason IS NULL
            )
        );

ALTER TABLE goal
    ADD CONSTRAINT ck_goal_priority_range
        CHECK (priority BETWEEN 1 AND 5),
    ADD CONSTRAINT ck_goal_target_value_non_negative
        CHECK (target_value IS NULL OR target_value >= 0),
    ADD CONSTRAINT ck_goal_baseline_value_non_negative
        CHECK (baseline_value IS NULL OR baseline_value >= 0),
    ADD CONSTRAINT ck_goal_archive_fields
        CHECK (
            (
                status = 'ARCHIVED'
                AND archived_at IS NOT NULL
                AND archive_reason IS NOT NULL
                AND btrim(archive_reason) <> ''
            )
            OR (
                status <> 'ARCHIVED'
                AND archived_at IS NULL
                AND archive_reason IS NULL
            )
        );
