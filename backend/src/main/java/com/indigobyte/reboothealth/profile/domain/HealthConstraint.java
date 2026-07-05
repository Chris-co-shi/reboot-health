package com.indigobyte.reboothealth.profile.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

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

    public HealthConstraint() {
    }

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

    public void changeStatus(ConstraintStatus targetStatus, Instant now) {
        assertEditable();
        status.assertCanTransitionTo(targetStatus);
        this.status = targetStatus;
        this.updatedAt = now;
    }

    public void archive(String archiveReason, Instant now) {
        if (archiveReason == null || archiveReason.isBlank()) {
            throw new DomainException(ErrorCode.VALIDATION_ERROR, "归档原因不能为空");
        }
        status.assertCanTransitionTo(ConstraintStatus.ARCHIVED);
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

    public void setId(UUID id) {
        this.id = id;
    }

    public ConstraintType getConstraintType() {
        return constraintType;
    }

    public void setConstraintType(ConstraintType constraintType) {
        this.constraintType = constraintType;
    }

    public BodyRegion getBodyRegion() {
        return bodyRegion;
    }

    public void setBodyRegion(BodyRegion bodyRegion) {
        this.bodyRegion = bodyRegion;
    }

    public ConstraintSeverity getSeverity() {
        return severity;
    }

    public void setSeverity(ConstraintSeverity severity) {
        this.severity = severity;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public ConstraintSourceType getSourceType() {
        return sourceType;
    }

    public void setSourceType(ConstraintSourceType sourceType) {
        this.sourceType = sourceType;
    }

    public String getSourceNote() {
        return sourceNote;
    }

    public void setSourceNote(String sourceNote) {
        this.sourceNote = sourceNote;
    }

    public ConstraintStatus getStatus() {
        return status;
    }

    public void setStatus(ConstraintStatus status) {
        this.status = status;
    }

    public LocalDate getEffectiveFrom() {
        return effectiveFrom;
    }

    public void setEffectiveFrom(LocalDate effectiveFrom) {
        this.effectiveFrom = effectiveFrom;
    }

    public LocalDate getEffectiveTo() {
        return effectiveTo;
    }

    public void setEffectiveTo(LocalDate effectiveTo) {
        this.effectiveTo = effectiveTo;
    }

    public String getArchiveReason() {
        return archiveReason;
    }

    public void setArchiveReason(String archiveReason) {
        this.archiveReason = archiveReason;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }

    public Instant getArchivedAt() {
        return archivedAt;
    }

    public void setArchivedAt(Instant archivedAt) {
        this.archivedAt = archivedAt;
    }
}
