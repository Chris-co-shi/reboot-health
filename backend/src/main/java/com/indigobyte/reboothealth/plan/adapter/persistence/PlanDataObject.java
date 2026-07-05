package com.indigobyte.reboothealth.plan.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;
import java.util.UUID;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * plan 表的持久化对象。
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@TableName("plan")
public class PlanDataObject {

    @TableId(value = "id", type = IdType.INPUT)
    private UUID id;

    @TableField("title")
    private String title;

    @TableField("summary")
    private String summary;

    @TableField("created_at")
    private Instant createdAt;

    @TableField("updated_at")
    private Instant updatedAt;
}
