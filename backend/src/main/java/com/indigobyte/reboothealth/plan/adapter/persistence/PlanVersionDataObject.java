package com.indigobyte.reboothealth.plan.adapter.persistence;

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
 * plan_version 表的持久化对象。
 *
 * <p>枚举以 String 保存；healthConstraintSnapshot 是 JSONB 文本，由专用 SQL 显式 CAST。</p>
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@TableName("plan_version")
public class PlanVersionDataObject {

    @TableId(value = "id", type = IdType.INPUT)
    private UUID id;

    @TableField("plan_id")
    private UUID planId;

    @TableField("version_number")
    private Integer versionNumber;

    @TableField("period_revision")
    private Integer periodRevision;

    @TableField("status")
    private String status;

    @TableField("start_date")
    private LocalDate startDate;

    @TableField("end_date")
    private LocalDate endDate;

    @TableField("title")
    private String title;

    @TableField("summary")
    private String summary;

    @TableField("copied_from_version_id")
    private UUID copiedFromVersionId;

    @TableField("supersedes_version_id")
    private UUID supersedesVersionId;

    @TableField("health_constraint_snapshot")
    private String healthConstraintSnapshot;

    @TableField("revision")
    private Integer revision;

    @TableField("confirmed_at")
    private Instant confirmedAt;

    @TableField("superseded_at")
    private Instant supersededAt;

    @TableField("cancelled_at")
    private Instant cancelledAt;

    @TableField("cancel_reason")
    private String cancelReason;

    @TableField("created_at")
    private Instant createdAt;

    @TableField("updated_at")
    private Instant updatedAt;
}
