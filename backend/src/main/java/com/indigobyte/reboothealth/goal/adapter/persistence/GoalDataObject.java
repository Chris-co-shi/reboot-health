package com.indigobyte.reboothealth.goal.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * goal 表的持久化对象。
 *
 * <p>该对象只服务 MyBatis-Plus 映射，领域状态机和目标单位校验仍由 Goal 聚合负责。</p>
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@TableName("goal")
public class GoalDataObject {

    @TableId(value = "id", type = IdType.INPUT)
    private UUID id;

    @TableField("goal_type")
    private String goalType;

    @TableField("title")
    private String title;

    @TableField("target_value")
    private BigDecimal targetValue;

    @TableField("unit")
    private String unit;

    @TableField("baseline_value")
    private BigDecimal baselineValue;

    @TableField("target_date")
    private LocalDate targetDate;

    @TableField("status")
    private String status;

    @TableField("priority")
    private Integer priority;

    @TableField("archive_reason")
    private String archiveReason;

    @TableField("created_at")
    private Instant createdAt;

    @TableField("updated_at")
    private Instant updatedAt;

    @TableField("archived_at")
    private Instant archivedAt;
}
