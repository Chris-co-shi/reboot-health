package com.indigobyte.reboothealth.plan.adapter.api;

import com.indigobyte.reboothealth.plan.domain.PlanItemType;
import com.indigobyte.reboothealth.plan.domain.PlanVersionStatus;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

/**
 * Plan 模块 REST 请求 DTO 集合。
 */
public final class PlanRequests {

    private PlanRequests() {
    }

    public record CreatePlanRequest(
            @NotBlank @Size(max = 100) String title,
            @Size(max = 1000) String summary
    ) {
    }

    public record CreateDraftRequest(
            @NotNull LocalDate startDate,
            @NotBlank @Size(max = 100) String title,
            @Size(max = 1000) String summary,
            List<UUID> goalIds
    ) {
    }

    public record UpdateVersionRequest(
            @NotBlank @Size(max = 100) String title,
            @Size(max = 1000) String summary,
            List<UUID> goalIds,
            @NotNull @Min(0) Integer expectedRevision
    ) {
    }

    public record CopyVersionRequest(
            @NotNull LocalDate startDate,
            @Size(max = 100) String title,
            @Size(max = 1000) String summary,
            PlanVersionStatus expectedSourceStatus
    ) {
    }

    public record ConfirmVersionRequest(
            @NotNull @Min(0) Integer expectedRevision
    ) {
    }

    public record CancelVersionRequest(
            @NotBlank @Size(max = 300) String cancelReason,
            @NotNull @Min(0) Integer expectedRevision
    ) {
    }

    public record SaveDayRequest(
            @NotNull LocalDate dayDate,
            @NotBlank @Size(max = 100) String title,
            @Size(max = 1000) String note,
            @NotNull @Min(1) @Max(7) Integer sortOrder,
            @NotNull @Min(0) Integer expectedRevision
    ) {
    }

    public record SaveItemRequest(
            UUID goalId,
            @NotNull PlanItemType itemType,
            @NotBlank @Size(max = 100) String title,
            @Size(max = 1000) String description,
            @DecimalMin("0.0") BigDecimal plannedSets,
            @DecimalMin("0.0") BigDecimal plannedReps,
            @DecimalMin("0.0") BigDecimal plannedDurationMinutes,
            @DecimalMin("0.0") BigDecimal plannedDistanceMeters,
            @DecimalMin("1.0") @DecimalMax("10.0") BigDecimal plannedRpe,
            @NotNull @Min(1) Integer sortOrder,
            @NotNull @Min(0) Integer expectedRevision
    ) {
    }
}
