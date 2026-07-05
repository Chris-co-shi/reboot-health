package com.indigobyte.reboothealth.plan.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * 计划日中的人工计划条目。
 *
 * <p>M2B 只记录计划量和描述，不建立动作库，也不记录执行结果。</p>
 */
public class PlanItem {

    private final UUID id;
    private final UUID dayId;
    private UUID goalId;
    private PlanItemType itemType;
    private String title;
    private String description;
    private BigDecimal plannedSets;
    private BigDecimal plannedReps;
    private BigDecimal plannedDurationMinutes;
    private BigDecimal plannedDistanceMeters;
    private BigDecimal plannedRpe;
    private int sortOrder;
    private final Instant createdAt;
    private Instant updatedAt;

    public PlanItem(UUID id, UUID dayId, UUID goalId, PlanItemType itemType, String title, String description,
                    BigDecimal plannedSets, BigDecimal plannedReps, BigDecimal plannedDurationMinutes,
                    BigDecimal plannedDistanceMeters, BigDecimal plannedRpe, int sortOrder,
                    Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.dayId = dayId;
        this.goalId = goalId;
        this.itemType = itemType;
        this.title = title;
        this.description = description;
        this.plannedSets = plannedSets;
        this.plannedReps = plannedReps;
        this.plannedDurationMinutes = plannedDurationMinutes;
        this.plannedDistanceMeters = plannedDistanceMeters;
        this.plannedRpe = plannedRpe;
        this.sortOrder = sortOrder;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
        validate();
    }

    public static PlanItem create(UUID dayId, UUID goalId, PlanItemType itemType, String title, String description,
                                  BigDecimal plannedSets, BigDecimal plannedReps, BigDecimal plannedDurationMinutes,
                                  BigDecimal plannedDistanceMeters, BigDecimal plannedRpe, int sortOrder, Instant now) {
        return new PlanItem(UUID.randomUUID(), dayId, goalId, itemType, title, description, plannedSets, plannedReps,
                plannedDurationMinutes, plannedDistanceMeters, plannedRpe, sortOrder, now, now);
    }

    public void update(UUID goalId, PlanItemType itemType, String title, String description,
                       BigDecimal plannedSets, BigDecimal plannedReps, BigDecimal plannedDurationMinutes,
                       BigDecimal plannedDistanceMeters, BigDecimal plannedRpe, int sortOrder, Instant now) {
        this.goalId = goalId;
        this.itemType = itemType;
        this.title = title;
        this.description = description;
        this.plannedSets = plannedSets;
        this.plannedReps = plannedReps;
        this.plannedDurationMinutes = plannedDurationMinutes;
        this.plannedDistanceMeters = plannedDistanceMeters;
        this.plannedRpe = plannedRpe;
        this.sortOrder = sortOrder;
        this.updatedAt = now;
        validate();
    }

    private void validate() {
        if (itemType == null || title == null || title.isBlank() || sortOrder < 1) {
            throw new DomainException(ErrorCode.PLAN_ITEM_INVALID_VALUE, "计划条目的类型、标题和顺序必须有效");
        }
        if (isNegative(plannedSets) || isNegative(plannedReps) || isNegative(plannedDurationMinutes)
                || isNegative(plannedDistanceMeters)) {
            throw new DomainException(ErrorCode.PLAN_ITEM_INVALID_VALUE, "计划条目数值不能为负数");
        }
        if (plannedRpe != null && (plannedRpe.compareTo(BigDecimal.ONE) < 0
                || plannedRpe.compareTo(BigDecimal.TEN) > 0)) {
            throw new DomainException(ErrorCode.PLAN_ITEM_INVALID_VALUE, "RPE 必须在 1 到 10 之间");
        }
    }

    private boolean isNegative(BigDecimal value) {
        return value != null && value.signum() < 0;
    }

    public UUID getId() {
        return id;
    }

    public UUID getDayId() {
        return dayId;
    }

    public UUID getGoalId() {
        return goalId;
    }

    public PlanItemType getItemType() {
        return itemType;
    }

    public String getTitle() {
        return title;
    }

    public String getDescription() {
        return description;
    }

    public BigDecimal getPlannedSets() {
        return plannedSets;
    }

    public BigDecimal getPlannedReps() {
        return plannedReps;
    }

    public BigDecimal getPlannedDurationMinutes() {
        return plannedDurationMinutes;
    }

    public BigDecimal getPlannedDistanceMeters() {
        return plannedDistanceMeters;
    }

    public BigDecimal getPlannedRpe() {
        return plannedRpe;
    }

    public int getSortOrder() {
        return sortOrder;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
