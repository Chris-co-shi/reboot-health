package com.indigobyte.reboothealth.profile.adapter.api;

import com.indigobyte.reboothealth.profile.domain.Sex;
import com.indigobyte.reboothealth.profile.domain.UserProfile;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

/**
 * 个人档案 API 响应对象。
 *
 * <p>用于将领域层的 UserProfile 转换为 REST API 响应格式，不包含敏感信息。</p>
 *
 * @param id 档案唯一标识符
 * @param displayName 用户显示名称
 * @param sex 性别
 * @param birthDate 出生日期
 * @param heightCm 身高（厘米）
 * @param baselineWeightKg 基线体重（千克）
 * @param timezone 时区标识
 * @param createdAt 创建时间
 * @param updatedAt 最后更新时间
 */
public record UserProfileResponse(
        UUID id,
        String displayName,
        Sex sex,
        LocalDate birthDate,
        BigDecimal heightCm,
        BigDecimal baselineWeightKg,
        String timezone,
        Instant createdAt,
        Instant updatedAt
) {
    /**
     * 从领域对象转换为 API 响应对象。
     *
     * @param profile 领域层的个人档案对象
     * @return API 响应对象
     */
    public static UserProfileResponse from(UserProfile profile) {
        return new UserProfileResponse(
                profile.getId(),
                profile.getDisplayName(),
                profile.getSex(),
                profile.getBirthDate(),
                profile.getHeightCm(),
                profile.getBaselineWeightKg(),
                profile.getTimezone(),
                profile.getCreatedAt(),
                profile.getUpdatedAt()
        );
    }
}
