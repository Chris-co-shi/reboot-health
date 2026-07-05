package com.indigobyte.reboothealth.profile.adapter.api;

import com.indigobyte.reboothealth.profile.domain.BodyRegion;
import com.indigobyte.reboothealth.profile.domain.ConstraintSeverity;
import com.indigobyte.reboothealth.profile.domain.ConstraintSourceType;
import com.indigobyte.reboothealth.profile.domain.ConstraintStatus;
import com.indigobyte.reboothealth.profile.domain.ConstraintType;
import com.indigobyte.reboothealth.profile.domain.HealthConstraint;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

/**
 * 健康约束 API 响应对象。
 *
 * <p>用于将领域层的 HealthConstraint 转换为 REST API 响应格式，包含所有业务字段和审计时间戳。</p>
 *
 * @param id 约束唯一标识符
 * @param constraintType 约束类型
 * @param bodyRegion 身体部位
 * @param severity 严重程度
 * @param title 约束标题
 * @param description 详细描述
 * @param sourceType 来源类型
 * @param sourceNote 来源备注
 * @param status 当前状态
 * @param effectiveFrom 生效开始日期
 * @param effectiveTo 生效结束日期
 * @param archiveReason 归档原因，未归档时为 null
 * @param createdAt 创建时间
 * @param updatedAt 最后更新时间
 * @param archivedAt 归档时间，未归档时为 null
 */
public record HealthConstraintResponse(
        UUID id,
        ConstraintType constraintType,
        BodyRegion bodyRegion,
        ConstraintSeverity severity,
        String title,
        String description,
        ConstraintSourceType sourceType,
        String sourceNote,
        ConstraintStatus status,
        LocalDate effectiveFrom,
        LocalDate effectiveTo,
        String archiveReason,
        Instant createdAt,
        Instant updatedAt,
        Instant archivedAt
) {
    /**
     * 从领域对象转换为 API 响应对象。
     *
     * @param constraint 领域层的健康约束对象
     * @return API 响应对象
     */
    public static HealthConstraintResponse from(HealthConstraint constraint) {
        return new HealthConstraintResponse(
                constraint.getId(),
                constraint.getConstraintType(),
                constraint.getBodyRegion(),
                constraint.getSeverity(),
                constraint.getTitle(),
                constraint.getDescription(),
                constraint.getSourceType(),
                constraint.getSourceNote(),
                constraint.getStatus(),
                constraint.getEffectiveFrom(),
                constraint.getEffectiveTo(),
                constraint.getArchiveReason(),
                constraint.getCreatedAt(),
                constraint.getUpdatedAt(),
                constraint.getArchivedAt()
        );
    }
}
