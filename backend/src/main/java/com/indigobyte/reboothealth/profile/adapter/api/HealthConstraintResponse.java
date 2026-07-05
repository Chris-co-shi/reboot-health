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
