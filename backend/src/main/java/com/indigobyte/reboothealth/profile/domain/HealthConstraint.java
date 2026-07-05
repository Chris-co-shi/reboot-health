package com.indigobyte.reboothealth.profile.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

/**
 * 健康约束聚合。
 *
 * <p>约束由用户手动维护，后续规则引擎和 AI 只能读取当前有效约束，不能删除或自动停用约束。</p>
 */
public class HealthConstraint {

    private UUID id;
    private ConstraintType constraintType;
    private BodyRegion bodyRegion;
    private ConstraintSeverity severity;
    private String title;
    private String description;
    private ConstraintSourceType sourceType;
    private String sourceNote;
    private ConstraintStatus status;
    private LocalDate effectiveFrom;
    private LocalDate effectiveTo;
    private String archiveReason;
    private Instant createdAt;
    private Instant updatedAt;
    private Instant archivedAt;

    public HealthConstraint(UUID id, ConstraintType constraintType, BodyRegion bodyRegion, ConstraintSeverity severity,
                            String title, String description, ConstraintSourceType sourceType, String sourceNote,
                            ConstraintStatus status, LocalDate effectiveFrom, LocalDate effectiveTo,
                            String archiveReason, Instant createdAt, Instant updatedAt, Instant archivedAt) {
        this.id = id;
        this.constraintType = constraintType;
        this.bodyRegion = bodyRegion;
        this.severity = severity;
        this.title = title;
        this.description = description;
        this.sourceType = sourceType;
        this.sourceNote = sourceNote;
        this.status = status;
        this.effectiveFrom = effectiveFrom;
        this.effectiveTo = effectiveTo;
        this.archiveReason = archiveReason;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
        this.archivedAt = archivedAt;
    }

    public static HealthConstraint create(ConstraintType constraintType, BodyRegion bodyRegion,
                                          ConstraintSeverity severity, String title, String description,
                                          ConstraintSourceType sourceType, String sourceNote,
                                          LocalDate effectiveFrom, LocalDate effectiveTo, Instant now) {
        assertValidDateRange(effectiveFrom, effectiveTo);
        return new HealthConstraint(UUID.randomUUID(), constraintType, bodyRegion, severity, title, description,
                sourceType, sourceNote, ConstraintStatus.ACTIVE, effectiveFrom, effectiveTo, null, now, now, null);
    }

    /**
     * 修改普通业务字段。已归档约束不能编辑，防止历史约束被无痕改写。
     */
    public void update(ConstraintType constraintType, BodyRegion bodyRegion, ConstraintSeverity severity,
                       String title, String description, ConstraintSourceType sourceType, String sourceNote,
                       LocalDate effectiveFrom, LocalDate effectiveTo, Instant now) {
        assertEditable();
        assertValidDateRange(effectiveFrom, effectiveTo);
        this.constraintType = constraintType;
        this.bodyRegion = bodyRegion;
        this.severity = severity;
        this.title = title;
        this.description = description;
        this.sourceType = sourceType;
        this.sourceNote = sourceNote;
        this.effectiveFrom = effectiveFrom;
        this.effectiveTo = effectiveTo;
        this.updatedAt = now;
    }

    /**
     * 普通状态流转不允许进入 ARCHIVED；归档必须走 archive 并提供原因。
     */
    public void changeStatus(ConstraintStatus targetStatus, Instant now) {
        assertEditable();
        status.assertCanTransitionTo(targetStatus);
        this.status = targetStatus;
        this.updatedAt = now;
    }

    /**
     * 将约束归档。归档是隐藏保留历史的终态，必须保留用户填写的原因和归档时间。
     */
    public void archive(String archiveReason, Instant now) {
        if (archiveReason == null || archiveReason.isBlank()) {
            throw new DomainException(ErrorCode.VALIDATION_ERROR, "归档原因不能为空");
        }
        status.assertCanArchive();
        this.status = ConstraintStatus.ARCHIVED;
        this.archiveReason = archiveReason;
        this.updatedAt = now;
        this.archivedAt = now;
    }

    private void assertEditable() {
        if (status == ConstraintStatus.ARCHIVED) {
            throw new DomainException(ErrorCode.HEALTH_CONSTRAINT_ARCHIVED, "已归档的健康约束不能编辑");
        }
    }

    private static void assertValidDateRange(LocalDate effectiveFrom, LocalDate effectiveTo) {
        if (effectiveFrom != null && effectiveTo != null && effectiveTo.isBefore(effectiveFrom)) {
            throw new DomainException(
                    ErrorCode.HEALTH_CONSTRAINT_INVALID_DATE_RANGE,
                    "健康约束结束日期不能早于开始日期"
            );
        }
    }

    public UUID getId() {
        return id;
    }

    public ConstraintType getConstraintType() {
        return constraintType;
    }

    public BodyRegion getBodyRegion() {
        return bodyRegion;
    }

    public ConstraintSeverity getSeverity() {
        return severity;
    }

    public String getTitle() {
        return title;
    }

    public String getDescription() {
        return description;
    }

    public ConstraintSourceType getSourceType() {
        return sourceType;
    }

    public String getSourceNote() {
        return sourceNote;
    }

    public ConstraintStatus getStatus() {
        return status;
    }

    public LocalDate getEffectiveFrom() {
        return effectiveFrom;
    }

    public LocalDate getEffectiveTo() {
        return effectiveTo;
    }

    public String getArchiveReason() {
        return archiveReason;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public Instant getArchivedAt() {
        return archivedAt;
    }
}
