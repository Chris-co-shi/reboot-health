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

    @Delete("DELETE FROM plan_version_goal WHERE version_id = #{versionId}")
    void deleteByVersionId(@Param("versionId") UUID versionId);

    @Insert("""
            INSERT INTO plan_version_goal (version_id, goal_id, created_at)
            VALUES (#{versionId}, #{goalId}, #{createdAt})
            """)
    void insertLink(@Param("versionId") UUID versionId, @Param("goalId") UUID goalId, @Param("createdAt") Instant createdAt);
}
