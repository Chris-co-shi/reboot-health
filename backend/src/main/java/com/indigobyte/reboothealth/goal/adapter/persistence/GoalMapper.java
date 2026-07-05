package com.indigobyte.reboothealth.goal.adapter.persistence;

import com.indigobyte.reboothealth.goal.domain.Goal;
import com.indigobyte.reboothealth.goal.domain.GoalStatus;
import java.util.List;
import java.util.UUID;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface GoalMapper {

    @Select("SELECT * FROM goal WHERE id = #{id}")
    Goal findById(UUID id);

    @Select("""
            <script>
            SELECT * FROM goal
            WHERE 1 = 1
            <if test="status != null">
              AND status = #{status}
            </if>
            <if test="status == null and includeArchived == false">
              AND status != 'ARCHIVED'
            </if>
            ORDER BY priority ASC, created_at DESC
            </script>
            """)
    List<Goal> findAll(@Param("status") GoalStatus status, @Param("includeArchived") boolean includeArchived);

    @Insert("""
            INSERT INTO goal (
                id, goal_type, title, target_value, unit, baseline_value,
                target_date, status, priority, archive_reason, created_at, updated_at, archived_at
            ) VALUES (
                #{id}, #{goalType}, #{title}, #{targetValue}, #{unit}, #{baselineValue},
                #{targetDate}, #{status}, #{priority}, #{archiveReason}, #{createdAt}, #{updatedAt}, #{archivedAt}
            )
            """)
    void insert(Goal goal);

    @Update("""
            UPDATE goal
            SET goal_type = #{goalType},
                title = #{title},
                target_value = #{targetValue},
                unit = #{unit},
                baseline_value = #{baselineValue},
                target_date = #{targetDate},
                status = #{status},
                priority = #{priority},
                archive_reason = #{archiveReason},
                updated_at = #{updatedAt},
                archived_at = #{archivedAt}
            WHERE id = #{id}
            """)
    void update(Goal goal);
}
