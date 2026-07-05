package com.indigobyte.reboothealth.plan.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import java.time.LocalDate;
import java.util.UUID;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

/**
 * plan_version 表 Mapper。
 *
 * <p>health_constraint_snapshot 是 JSONB，写入和更新必须显式 CAST，不能依赖普通字符串隐式转换。</p>
 */
@Mapper
public interface PlanVersionMapper extends BaseMapper<PlanVersionDataObject> {

    @Select("""
            SELECT id, plan_id, version_number, period_revision, status, start_date, end_date,
                   title, summary, copied_from_version_id, supersedes_version_id,
                   health_constraint_snapshot::text AS health_constraint_snapshot,
                   revision, confirmed_at, superseded_at, cancelled_at, cancel_reason, created_at, updated_at
            FROM plan_version
            WHERE id = #{id}
            """)
    PlanVersionDataObject selectVersionById(@Param("id") UUID id);

    @Select("""
            SELECT id, plan_id, version_number, period_revision, status, start_date, end_date,
                   title, summary, copied_from_version_id, supersedes_version_id,
                   health_constraint_snapshot::text AS health_constraint_snapshot,
                   revision, confirmed_at, superseded_at, cancelled_at, cancel_reason, created_at, updated_at
            FROM plan_version
            WHERE plan_id = #{planId}
            ORDER BY start_date DESC, period_revision DESC
            """)
    java.util.List<PlanVersionDataObject> selectVersions(@Param("planId") UUID planId);

    @Select("""
            SELECT id, plan_id, version_number, period_revision, status, start_date, end_date,
                   title, summary, copied_from_version_id, supersedes_version_id,
                   health_constraint_snapshot::text AS health_constraint_snapshot,
                   revision, confirmed_at, superseded_at, cancelled_at, cancel_reason, created_at, updated_at
            FROM plan_version
            WHERE plan_id = #{planId} AND status = #{status}
            ORDER BY start_date DESC, period_revision DESC
            """)
    java.util.List<PlanVersionDataObject> selectVersionsByStatus(@Param("planId") UUID planId, @Param("status") String status);

    @Select("""
            SELECT id, plan_id, version_number, period_revision, status, start_date, end_date,
                   title, summary, copied_from_version_id, supersedes_version_id,
                   health_constraint_snapshot::text AS health_constraint_snapshot,
                   revision, confirmed_at, superseded_at, cancelled_at, cancel_reason, created_at, updated_at
            FROM plan_version
            WHERE id = #{id}
            FOR UPDATE
            """)
    PlanVersionDataObject selectByIdForUpdate(@Param("id") UUID id);

    @Select("""
            SELECT id, plan_id, version_number, period_revision, status, start_date, end_date,
                   title, summary, copied_from_version_id, supersedes_version_id,
                   health_constraint_snapshot::text AS health_constraint_snapshot,
                   revision, confirmed_at, superseded_at, cancelled_at, cancel_reason, created_at, updated_at
            FROM plan_version
            WHERE plan_id = #{planId} AND start_date = #{startDate} AND status = 'CONFIRMED'
            FOR UPDATE
            """)
    PlanVersionDataObject selectConfirmedForPeriodForUpdate(@Param("planId") UUID planId,
                                                            @Param("startDate") LocalDate startDate);

    @Select("""
            SELECT id, plan_id, version_number, period_revision, status, start_date, end_date,
                   title, summary, copied_from_version_id, supersedes_version_id,
                   health_constraint_snapshot::text AS health_constraint_snapshot,
                   revision, confirmed_at, superseded_at, cancelled_at, cancel_reason, created_at, updated_at
            FROM plan_version
            WHERE status = 'CONFIRMED' AND start_date <= #{currentDate} AND end_date >= #{currentDate}
            ORDER BY start_date DESC
            LIMIT 1
            """)
    PlanVersionDataObject selectCurrentConfirmed(@Param("currentDate") LocalDate currentDate);

    @Select("SELECT COALESCE(MAX(version_number), 0) + 1 FROM plan_version WHERE plan_id = #{planId}")
    int selectNextVersionNumber(@Param("planId") UUID planId);

    @Select("""
            SELECT COALESCE(MAX(period_revision), -1) + 1
            FROM plan_version
            WHERE plan_id = #{planId} AND start_date = #{startDate}
            """)
    int selectNextPeriodRevision(@Param("planId") UUID planId, @Param("startDate") LocalDate startDate);

    @Insert("""
            INSERT INTO plan_version (
                id, plan_id, version_number, period_revision, status, start_date, end_date,
                title, summary, copied_from_version_id, supersedes_version_id, health_constraint_snapshot,
                revision, confirmed_at, superseded_at, cancelled_at, cancel_reason, created_at, updated_at
            ) VALUES (
                #{id}, #{planId}, #{versionNumber}, #{periodRevision}, #{status}, #{startDate}, #{endDate},
                #{title}, #{summary}, #{copiedFromVersionId}, #{supersedesVersionId},
                CAST(#{healthConstraintSnapshot} AS jsonb),
                #{revision}, #{confirmedAt}, #{supersededAt}, #{cancelledAt}, #{cancelReason}, #{createdAt}, #{updatedAt}
            )
            """)
    int insertVersion(PlanVersionDataObject dataObject);

    @Update("""
            UPDATE plan_version
            SET status = #{status},
                title = #{title},
                summary = #{summary},
                supersedes_version_id = #{supersedesVersionId},
                health_constraint_snapshot = CAST(#{healthConstraintSnapshot} AS jsonb),
                revision = #{revision},
                confirmed_at = #{confirmedAt},
                superseded_at = #{supersededAt},
                cancelled_at = #{cancelledAt},
                cancel_reason = #{cancelReason},
                updated_at = #{updatedAt}
            WHERE id = #{id}
            """)
    int updateVersion(PlanVersionDataObject dataObject);
}
