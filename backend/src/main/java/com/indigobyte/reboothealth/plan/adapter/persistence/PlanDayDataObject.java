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
 * plan_day 表的持久化对象。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@TableName("plan_day")
public class PlanDayDataObject {

    @TableId(value = "id", type = IdType.INPUT)
    private UUID id;

    @TableField("version_id")
    private UUID versionId;

    @TableField("day_date")
    private LocalDate dayDate;

    @TableField("title")
    private String title;

    @TableField("note")
    private String note;

    @TableField("sort_order")
    private Integer sortOrder;

    @TableField("created_at")
    private Instant createdAt;

    @TableField("updated_at")
    private Instant updatedAt;
}
