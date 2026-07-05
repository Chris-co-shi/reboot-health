package com.indigobyte.reboothealth.profile.adapter.api;

import com.indigobyte.reboothealth.profile.domain.BodyRegion;
import com.indigobyte.reboothealth.profile.domain.ConstraintSeverity;
import com.indigobyte.reboothealth.profile.domain.ConstraintSourceType;
import com.indigobyte.reboothealth.profile.domain.ConstraintType;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;

/**
 * 健康约束请求记录。
 * <p>
 * 用于接收客户端创建或更新用户健康约束（如伤病、禁忌动作等）的请求数据。
 * 包含约束类型、身体部位、严重程度、标题、描述、来源信息及有效日期范围。
 * </p>
 *
 * @param constraintType 约束类型（例如：伤病、手术、禁忌等）
 * @param bodyRegion     受影响的_body_区域
 * @param severity       约束严重程度
 * @param title          约束标题，非空且最大长度100字符
 * @param description    约束详细描述，最大长度2000字符
 * @param sourceType     约束来源类型（例如：用户自述、医生诊断、AI建议等）
 * @param sourceNote     来源备注信息，最大长度1000字符
 * @param effectiveFrom  生效开始日期
 * @param effectiveTo    生效结束日期
 */
public record HealthConstraintRequest(
        @NotNull ConstraintType constraintType,
        @NotNull BodyRegion bodyRegion,
        @NotNull ConstraintSeverity severity,
        @NotBlank @Size(max = 100) String title,
        @Size(max = 2000) String description,
        @NotNull ConstraintSourceType sourceType,
        @Size(max = 1000) String sourceNote,
        LocalDate effectiveFrom,
        LocalDate effectiveTo
) {
    /**
     * 验证有效日期范围的合法性。
     * <p>
     * 如果开始日期和结束日期均不为空，则结束日期不能早于开始日期。
     * </p>
     *
     * @return 如果日期范围有效（即至少一个日期为空，或结束日期不早于开始日期）则返回 true
     */
    @AssertTrue(message = "effectiveTo 不能早于 effectiveFrom")
    public boolean isDateRangeValid() {
        return effectiveFrom == null || effectiveTo == null || !effectiveTo.isBefore(effectiveFrom);
    }
}
