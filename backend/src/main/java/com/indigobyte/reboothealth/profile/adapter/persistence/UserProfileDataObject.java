package com.indigobyte.reboothealth.profile.adapter.persistence;

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
 * app_user_profile 表的持久化对象。
 *
 * <p>字段保持数据库语义，枚举使用 String 存储，避免依赖 MyBatis 默认枚举处理。</p>
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@TableName("app_user_profile")
public class UserProfileDataObject {

    @TableId(value = "id", type = IdType.INPUT)
    private UUID id;

    @TableField("singleton_key")
    private Short singletonKey;

    @TableField("display_name")
    private String displayName;

    @TableField("sex")
    private String sex;

    @TableField("birth_date")
    private LocalDate birthDate;

    @TableField("height_cm")
    private BigDecimal heightCm;

    @TableField("baseline_weight_kg")
    private BigDecimal baselineWeightKg;

    @TableField("timezone")
    private String timezone;

    @TableField("created_at")
    private Instant createdAt;

    @TableField("updated_at")
    private Instant updatedAt;
}
