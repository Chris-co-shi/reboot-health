package com.indigobyte.reboothealth.profile.adapter.api;

import com.indigobyte.reboothealth.profile.domain.Sex;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PastOrPresent;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * 个人档案保存请求对象。
 *
 * <p>用于 PUT /api/v1/profile 接口，所有字段都经过校验注解约束。</p>
 *
 * @param displayName 显示名称，不能为空且最长 60 字符
 * @param sex 性别，不能为 null
 * @param birthDate 出生日期，必须是过去或今天的日期
 * @param heightCm 身高（厘米），范围 100.00 - 250.00
 * @param baselineWeightKg 基线体重（千克），范围 30.00 - 300.00
 * @param timezone 时区标识，不能为空且最长 64 字符，必须是合法的 IANA 时区
 */
public record UserProfileRequest(
        @NotBlank @Size(max = 60) String displayName,
        @NotNull Sex sex,
        @PastOrPresent LocalDate birthDate,
        @DecimalMin("100.00") @DecimalMax("250.00") BigDecimal heightCm,
        @DecimalMin("30.00") @DecimalMax("300.00") BigDecimal baselineWeightKg,
        @NotBlank @Size(max = 64) String timezone
) {
}
