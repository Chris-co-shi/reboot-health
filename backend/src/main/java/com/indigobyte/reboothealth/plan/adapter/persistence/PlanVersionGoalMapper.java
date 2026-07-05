package com.indigobyte.reboothealth.plan.adapter.persistence;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * plan_version_goal 关联表 Mapper。
 */
@Mapper
public interface PlanVersionGoalMapper {

    @Select("SELECT goal_id FROM plan_version_goal WHERE version_id = #{versionId} ORDER BY goal_id")
    List<UUID> selectGoalIds(@Param("versionId") UUID versionId);

    @Select("""
            SELECT goal_id, goal_title, goal_type, goal_status, target_value, unit, baseline_value, target_date
            FROM plan_version_goal
            WHERE version_id = #{versionId}
            ORDER BY goal_id
            """)
    List<PlanVersionGoalSnapshotDataObject> selectGoalSnapshots(@Param("versionId") UUID versionId);

    @Delete("DELETE FROM plan_version_goal WHERE version_id = #{versionId}")
    void deleteByVersionId(@Param("versionId") UUID versionId);

    @Insert("""
            INSERT INTO plan_version_goal (version_id, goal_id, created_at)
            VALUES (#{versionId}, #{goalId}, #{createdAt})
            """)
    void insertLink(@Param("versionId") UUID versionId, @Param("goalId") UUID goalId, @Param("createdAt") Instant createdAt);

    @org.apache.ibatis.annotations.Update("""
            UPDATE plan_version_goal
            SET goal_title = #{goalTitle},
                goal_type = #{goalType},
                goal_status = #{goalStatus},
                target_value = #{targetValue},
                unit = #{unit},
                baseline_value = #{baselineValue},
                target_date = #{targetDate}
            WHERE version_id = #{versionId} AND goal_id = #{goalId}
            """)
    int updateGoalSnapshot(@Param("versionId") UUID versionId,
                           @Param("goalId") UUID goalId,
                           @Param("goalTitle") String goalTitle,
                           @Param("goalType") String goalType,
                           @Param("goalStatus") String goalStatus,
                           @Param("targetValue") java.math.BigDecimal targetValue,
                           @Param("unit") String unit,
                           @Param("baselineValue") java.math.BigDecimal baselineValue,
                           @Param("targetDate") java.time.LocalDate targetDate);
}
