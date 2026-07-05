package com.indigobyte.reboothealth.profile.adapter.persistence;

import com.indigobyte.reboothealth.profile.domain.ConstraintStatus;
import com.indigobyte.reboothealth.profile.domain.HealthConstraint;
import java.util.List;
import java.util.UUID;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface HealthConstraintMapper {

    @Select("SELECT * FROM health_constraint WHERE id = #{id}")
    HealthConstraint findById(UUID id);

    @Select("""
            <script>
            SELECT * FROM health_constraint
            WHERE 1 = 1
            <if test="status != null">
              AND status = #{status}
            </if>
            <if test="status == null and includeArchived == false">
              AND status != 'ARCHIVED'
            </if>
            ORDER BY created_at DESC
            </script>
            """)
    List<HealthConstraint> findAll(@Param("status") ConstraintStatus status, @Param("includeArchived") boolean includeArchived);

    @Insert("""
            INSERT INTO health_constraint (
                id, constraint_type, body_region, severity, title, description,
                source_type, source_note, status, effective_from, effective_to,
                archive_reason, created_at, updated_at, archived_at
            ) VALUES (
                #{id}, #{constraintType}, #{bodyRegion}, #{severity}, #{title}, #{description},
                #{sourceType}, #{sourceNote}, #{status}, #{effectiveFrom}, #{effectiveTo},
                #{archiveReason}, #{createdAt}, #{updatedAt}, #{archivedAt}
            )
            """)
    void insert(HealthConstraint constraint);

    @Update("""
            UPDATE health_constraint
            SET constraint_type = #{constraintType},
                body_region = #{bodyRegion},
                severity = #{severity},
                title = #{title},
                description = #{description},
                source_type = #{sourceType},
                source_note = #{sourceNote},
                status = #{status},
                effective_from = #{effectiveFrom},
                effective_to = #{effectiveTo},
                archive_reason = #{archiveReason},
                updated_at = #{updatedAt},
                archived_at = #{archivedAt}
            WHERE id = #{id}
            """)
    void update(HealthConstraint constraint);
}
