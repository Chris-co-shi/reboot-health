package com.indigobyte.reboothealth.profile.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * health_constraint 表的持久化对象。
 *
 * <p>所有领域枚举在 DO 中保存为 String，由 Converter 显式转换，避免 ordinal 或隐式 TypeHandler。</p>
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@TableName("health_constraint")
public class HealthConstraintDataObject {

    @TableId(value = "id", type = IdType.INPUT)
    private UUID id;

    @TableField("constraint_type")
    private String constraintType;

    @TableField("body_region")
    private String bodyRegion;

    @TableField("severity")
    private String severity;

    @TableField("title")
    private String title;

    @TableField("description")
    private String description;

    @TableField("source_type")
    private String sourceType;

    @TableField("source_note")
    private String sourceNote;

    @TableField("status")
    private String status;

    @TableField("effective_from")
    private LocalDate effectiveFrom;

    @TableField("effective_to")
    private LocalDate effectiveTo;

    @TableField("archive_reason")
    private String archiveReason;

    @TableField("created_at")
    private Instant createdAt;

    @TableField("updated_at")
    private Instant updatedAt;

    @TableField("archived_at")
    private Instant archivedAt;
}
