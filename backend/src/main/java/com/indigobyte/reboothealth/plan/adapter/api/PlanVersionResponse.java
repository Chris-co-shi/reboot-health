package com.indigobyte.reboothealth.plan.adapter.api;

import com.indigobyte.reboothealth.plan.domain.PlanDay;
import com.indigobyte.reboothealth.plan.domain.PlanDayDetail;
import com.indigobyte.reboothealth.plan.domain.PlanItem;
import com.indigobyte.reboothealth.plan.domain.PlanItemType;
import com.indigobyte.reboothealth.plan.domain.PlanVersion;
import com.indigobyte.reboothealth.plan.domain.PlanVersionDetail;
import com.indigobyte.reboothealth.plan.domain.PlanVersionPreview;
import com.indigobyte.reboothealth.plan.domain.PlanVersionStatus;
import com.indigobyte.reboothealth.plan.domain.GoalSummarySnapshot;
import com.indigobyte.reboothealth.plan.domain.HealthConstraintSnapshot;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

/**
 * 计划版本详情响应 DTO。
 */
public record PlanVersionResponse(
        UUID id,
        UUID planId,
        int versionNumber,
        int periodRevision,
        PlanVersionStatus status,
        LocalDate startDate,
        LocalDate endDate,
        String title,
        String summary,
        UUID copiedFromVersionId,
        UUID supersedesVersionId,
        int revision,
        Instant confirmedAt,
        Instant supersededAt,
        Instant cancelledAt,
        String cancelReason,
        Instant createdAt,
        Instant updatedAt,
        List<UUID> goalIds,
        List<GoalSummarySnapshot> goals,
        HealthConstraintSnapshot healthConstraints,
        List<PlanDayResponse> days
) {

    public static PlanVersionResponse from(PlanVersionDetail detail) {
        PlanVersion version = detail.version();
        return new PlanVersionResponse(
                version.getId(),
                version.getPlanId(),
                version.getVersionNumber(),
                version.getPeriodRevision(),
                version.getStatus(),
                version.getStartDate(),
                version.getEndDate(),
                version.getTitle(),
                version.getSummary(),
                version.getCopiedFromVersionId(),
                version.getSupersedesVersionId(),
                version.getRevision(),
                version.getConfirmedAt(),
                version.getSupersededAt(),
                version.getCancelledAt(),
                version.getCancelReason(),
                version.getCreatedAt(),
                version.getUpdatedAt(),
                detail.goalIds(),
                detail.goals(),
                detail.healthConstraints(),
                detail.days().stream().map(PlanDayResponse::from).toList()
        );
    }

    public static PlanVersionSummaryResponse summary(PlanVersion version) {
        return new PlanVersionSummaryResponse(
                version.getId(),
                version.getPlanId(),
                version.getVersionNumber(),
                version.getPeriodRevision(),
                version.getStatus(),
                version.getStartDate(),
                version.getEndDate(),
                version.getTitle(),
                version.getRevision(),
                version.getConfirmedAt(),
                version.getCreatedAt(),
                version.getUpdatedAt()
        );
    }

    public record PlanVersionSummaryResponse(
            UUID id,
            UUID planId,
            int versionNumber,
            int periodRevision,
            PlanVersionStatus status,
            LocalDate startDate,
            LocalDate endDate,
            String title,
            int revision,
            Instant confirmedAt,
            Instant createdAt,
            Instant updatedAt
    ) {
    }

    public record PlanDayResponse(
            UUID id,
            UUID versionId,
            LocalDate dayDate,
            String title,
            String note,
            int sortOrder,
            Instant createdAt,
            Instant updatedAt,
            List<PlanItemResponse> items
    ) {
        static PlanDayResponse from(PlanDayDetail detail) {
            PlanDay day = detail.day();
            return new PlanDayResponse(
                    day.getId(),
                    day.getVersionId(),
                    day.getDayDate(),
                    day.getTitle(),
                    day.getNote(),
                    day.getSortOrder(),
                    day.getCreatedAt(),
                    day.getUpdatedAt(),
                    detail.items().stream().map(PlanItemResponse::from).toList()
            );
        }
    }

    public record PlanItemResponse(
            UUID id,
            UUID dayId,
            UUID goalId,
            PlanItemType itemType,
            String title,
            String description,
            BigDecimal plannedSets,
            BigDecimal plannedReps,
            BigDecimal plannedDurationMinutes,
            BigDecimal plannedDistanceMeters,
            BigDecimal plannedRpe,
            int sortOrder,
            Instant createdAt,
            Instant updatedAt
    ) {
        static PlanItemResponse from(PlanItem item) {
            return new PlanItemResponse(
                    item.getId(),
                    item.getDayId(),
                    item.getGoalId(),
                    item.getItemType(),
                    item.getTitle(),
                    item.getDescription(),
                    item.getPlannedSets(),
                    item.getPlannedReps(),
                    item.getPlannedDurationMinutes(),
                    item.getPlannedDistanceMeters(),
                    item.getPlannedRpe(),
                    item.getSortOrder(),
                    item.getCreatedAt(),
                    item.getUpdatedAt()
            );
        }
    }
}

/**
 * 计划版本确认预览响应 DTO。
 */
record PlanVersionPreviewResponse(
        PlanVersionResponse detail,
        List<GoalSummarySnapshot> goals,
        HealthConstraintSnapshot healthConstraints,
        List<String> validationIssues,
        boolean canConfirm
) {

    static PlanVersionPreviewResponse from(PlanVersionPreview preview) {
        return new PlanVersionPreviewResponse(
                PlanVersionResponse.from(preview.detail()),
                preview.goals(),
                preview.healthConstraints(),
                preview.validationIssues(),
                preview.canConfirm()
        );
    }
}
