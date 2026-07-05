package com.indigobyte.reboothealth.plan.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * plan_item 表的持久化对象。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@TableName("plan_item")
public class PlanItemDataObject {

    @TableId(value = "id", type = IdType.INPUT)
    private UUID id;

    @TableField("day_id")
    private UUID dayId;

    @TableField("goal_id")
    private UUID goalId;

    @TableField("item_type")
    private String itemType;

    @TableField("title")
    private String title;

    @TableField("description")
    private String description;

    @TableField("planned_sets")
    private BigDecimal plannedSets;

    @TableField("planned_reps")
    private BigDecimal plannedReps;

    @TableField("planned_duration_minutes")
    private BigDecimal plannedDurationMinutes;

    @TableField("planned_distance_meters")
    private BigDecimal plannedDistanceMeters;

    @TableField("planned_rpe")
    private BigDecimal plannedRpe;

    @TableField("sort_order")
    private Integer sortOrder;

    @TableField("created_at")
    private Instant createdAt;

    @TableField("updated_at")
    private Instant updatedAt;
}
