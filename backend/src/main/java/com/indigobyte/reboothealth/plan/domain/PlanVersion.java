package com.indigobyte.reboothealth.plan.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.time.Instant;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.UUID;

/**
 * 计划版本聚合根。
 *
 * <p>版本一旦确认就不可原地修改；同周期修订通过新 DRAFT 确认后替代旧 CONFIRMED 版本。</p>
 */
public class PlanVersion {

    private final UUID id;
    private final UUID planId;
    private final int versionNumber;
    private final int periodRevision;
    private PlanVersionStatus status;
    private final LocalDate startDate;
    private final LocalDate endDate;
    private String title;
    private String summary;
    private final UUID copiedFromVersionId;
    private UUID supersedesVersionId;
    private String healthConstraintSnapshot;
    private int revision;
    private Instant confirmedAt;
    private Instant supersededAt;
    private Instant cancelledAt;
    private String cancelReason;
    private final Instant createdAt;
    private Instant updatedAt;

    public PlanVersion(UUID id, UUID planId, int versionNumber, int periodRevision, PlanVersionStatus status,
                       LocalDate startDate, LocalDate endDate, String title, String summary,
                       UUID copiedFromVersionId, UUID supersedesVersionId, String healthConstraintSnapshot,
                       int revision, Instant confirmedAt, Instant supersededAt, Instant cancelledAt,
                       String cancelReason, Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.planId = planId;
        this.versionNumber = versionNumber;
        this.periodRevision = periodRevision;
        this.status = status;
        this.startDate = startDate;
        this.endDate = endDate;
        this.title = title;
        this.summary = summary;
        this.copiedFromVersionId = copiedFromVersionId;
        this.supersedesVersionId = supersedesVersionId;
        this.healthConstraintSnapshot = healthConstraintSnapshot;
        this.revision = revision;
        this.confirmedAt = confirmedAt;
        this.supersededAt = supersededAt;
        this.cancelledAt = cancelledAt;
        this.cancelReason = cancelReason;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
        validatePeriod(startDate, endDate);
    }

    public static PlanVersion createDraft(UUID planId, int versionNumber, int periodRevision, LocalDate startDate,
                                          String title, String summary, UUID copiedFromVersionId, Instant now) {
        LocalDate endDate = startDate.plusDays(6);
        return new PlanVersion(UUID.randomUUID(), planId, versionNumber, periodRevision, PlanVersionStatus.DRAFT,
                startDate, endDate, title, summary, copiedFromVersionId, null, null,
                0, null, null, null, null, now, now);
    }

    /**
     * 修改草案元数据并增加 revision，用于 PUT 的乐观并发控制。
     */
    public void updateDraft(String title, String summary, Instant now) {
        assertDraft();
        this.title = title;
        this.summary = summary;
        touchWithRevision(now);
    }

    /**
     * 确认草案。确认后的版本不可再修改，健康约束快照固定在确认时。
     */
    public void confirm(UUID supersedesVersionId, String healthConstraintSnapshot, Instant now) {
        assertDraft();
        this.status = PlanVersionStatus.CONFIRMED;
        this.supersedesVersionId = supersedesVersionId;
        this.healthConstraintSnapshot = healthConstraintSnapshot;
        this.confirmedAt = now;
        touchWithRevision(now);
    }

    /**
     * 标记旧确认版本被同周期新版本替代。
     */
    public void supersede(Instant now) {
        if (status != PlanVersionStatus.CONFIRMED) {
            throw new DomainException(ErrorCode.PLAN_VERSION_IMMUTABLE, "只有已确认版本可以被替代");
        }
        this.status = PlanVersionStatus.SUPERSEDED;
        this.supersededAt = now;
        touchWithRevision(now);
    }

    /**
     * 取消草案。取消后的草案保留历史但不可恢复。
     */
    public void cancel(String reason, Instant now) {
        assertDraft();
        if (reason == null || reason.isBlank()) {
            throw new DomainException(ErrorCode.VALIDATION_ERROR, "取消原因不能为空");
        }
        this.status = PlanVersionStatus.CANCELLED;
        this.cancelReason = reason;
        this.cancelledAt = now;
        touchWithRevision(now);
    }

    public void touchDraftContent(Instant now) {
        assertDraft();
        touchWithRevision(now);
    }

    public void assertDraft() {
        if (status != PlanVersionStatus.DRAFT) {
            throw new DomainException(ErrorCode.PLAN_VERSION_NOT_DRAFT, "只有草案计划版本可以执行该操作");
        }
    }

    public void assertExpectedRevision(Integer expectedRevision) {
        if (expectedRevision == null || expectedRevision != revision) {
            throw new DomainException(ErrorCode.PLAN_VERSION_REVISION_CONFLICT, "计划版本已变化，请刷新后重试");
        }
    }

    private void touchWithRevision(Instant now) {
        this.revision += 1;
        this.updatedAt = now;
    }

    private static void validatePeriod(LocalDate startDate, LocalDate endDate) {
        if (startDate == null || endDate == null || ChronoUnit.DAYS.between(startDate, endDate) != 6) {
            throw new DomainException(ErrorCode.PLAN_VERSION_INVALID_PERIOD, "计划周期必须连续 7 天");
        }
    }

    public UUID getId() {
        return id;
    }

    public UUID getPlanId() {
        return planId;
    }

    public int getVersionNumber() {
        return versionNumber;
    }

    public int getPeriodRevision() {
        return periodRevision;
    }

    public PlanVersionStatus getStatus() {
        return status;
    }

    public LocalDate getStartDate() {
        return startDate;
    }

    public LocalDate getEndDate() {
        return endDate;
    }

    public String getTitle() {
        return title;
    }

    public String getSummary() {
        return summary;
    }

    public UUID getCopiedFromVersionId() {
        return copiedFromVersionId;
    }

    public UUID getSupersedesVersionId() {
        return supersedesVersionId;
    }

    public String getHealthConstraintSnapshot() {
        return healthConstraintSnapshot;
    }

    public int getRevision() {
        return revision;
    }

    public Instant getConfirmedAt() {
        return confirmedAt;
    }

    public Instant getSupersededAt() {
        return supersededAt;
    }

    public Instant getCancelledAt() {
        return cancelledAt;
    }

    public String getCancelReason() {
        return cancelReason;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
