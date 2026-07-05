package com.indigobyte.reboothealth.goal.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.Set;
import java.util.UUID;

public class Goal {

    private UUID id;
    private GoalType goalType;
    private String title;
    private BigDecimal targetValue;
    private GoalUnit unit;
    private BigDecimal baselineValue;
    private LocalDate targetDate;
    private GoalStatus status;
    private Integer priority;
    private String archiveReason;
    private Instant createdAt;
    private Instant updatedAt;
    private Instant archivedAt;

    public Goal() {
    }

    public Goal(UUID id, GoalType goalType, String title, BigDecimal targetValue, GoalUnit unit,
                BigDecimal baselineValue, LocalDate targetDate, GoalStatus status, Integer priority,
                String archiveReason, Instant createdAt, Instant updatedAt, Instant archivedAt) {
        this.id = id;
        this.goalType = goalType;
        this.title = title;
        this.targetValue = targetValue;
        this.unit = unit;
        this.baselineValue = baselineValue;
        this.targetDate = targetDate;
        this.status = status;
        this.priority = priority;
        this.archiveReason = archiveReason;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
        this.archivedAt = archivedAt;
    }

    public static Goal create(GoalType goalType, String title, BigDecimal targetValue, GoalUnit unit,
                              BigDecimal baselineValue, LocalDate targetDate, Integer priority, Instant now) {
        validateTarget(goalType, targetValue, unit, baselineValue);
        return new Goal(UUID.randomUUID(), goalType, title, targetValue, unit, baselineValue, targetDate,
                GoalStatus.ACTIVE, priority, null, now, now, null);
    }

    public void update(GoalType goalType, String title, BigDecimal targetValue, GoalUnit unit,
                       BigDecimal baselineValue, LocalDate targetDate, Integer priority, Instant now) {
        assertEditable();
        validateTarget(goalType, targetValue, unit, baselineValue);
        this.goalType = goalType;
        this.title = title;
        this.targetValue = targetValue;
        this.unit = unit;
        this.baselineValue = baselineValue;
        this.targetDate = targetDate;
        this.priority = priority;
        this.updatedAt = now;
    }

    public void changeStatus(GoalStatus targetStatus, Instant now) {
        assertEditable();
        status.assertCanTransitionTo(targetStatus);
        this.status = targetStatus;
        this.updatedAt = now;
    }

    public void archive(String archiveReason, Instant now) {
        if (archiveReason == null || archiveReason.isBlank()) {
            throw new DomainException(ErrorCode.VALIDATION_ERROR, "归档原因不能为空");
        }
        status.assertCanTransitionTo(GoalStatus.ARCHIVED);
        this.status = GoalStatus.ARCHIVED;
        this.archiveReason = archiveReason;
        this.updatedAt = now;
        this.archivedAt = now;
    }

    private void assertEditable() {
        if (status == GoalStatus.ARCHIVED) {
            throw new DomainException(ErrorCode.GOAL_ARCHIVED, "已归档的目标不能编辑");
        }
    }

    private static void validateTarget(GoalType goalType, BigDecimal targetValue, GoalUnit unit, BigDecimal baselineValue) {
        if (isNegative(targetValue) || isNegative(baselineValue)) {
            throw invalidTarget("目标值和基线值必须大于或等于 0");
        }
        if (unit == GoalUnit.NONE && (targetValue != null || baselineValue != null)) {
            throw invalidTarget("unit 为 NONE 时目标值和基线值应为空");
        }
        if (!allowedUnits(goalType).contains(unit)) {
            throw invalidTarget("目标类型和单位不匹配");
        }
    }

    private static Set<GoalUnit> allowedUnits(GoalType goalType) {
        return switch (goalType) {
            case WEIGHT -> Set.of(GoalUnit.KG);
            case WAIST -> Set.of(GoalUnit.CM);
            case TRAINING_HABIT -> Set.of(GoalUnit.SESSIONS_PER_WEEK);
            case SWIMMING -> Set.of(GoalUnit.METERS, GoalUnit.LAPS);
            case SLEEP -> Set.of(GoalUnit.MINUTES, GoalUnit.MINUTES_PER_DAY);
            case AEROBIC_CAPACITY, STRENGTH, BASKETBALL_CONDITIONING -> Set.of(GoalUnit.MINUTES, GoalUnit.SCORE, GoalUnit.PERCENT);
            case OTHER -> Set.of(GoalUnit.NONE, GoalUnit.KG, GoalUnit.CM, GoalUnit.SESSIONS_PER_WEEK,
                    GoalUnit.MINUTES, GoalUnit.MINUTES_PER_DAY, GoalUnit.METERS, GoalUnit.LAPS, GoalUnit.SCORE, GoalUnit.PERCENT);
        };
    }

    private static boolean isNegative(BigDecimal value) {
        return value != null && value.signum() < 0;
    }

    private static DomainException invalidTarget(String message) {
        return new DomainException(ErrorCode.GOAL_INVALID_TARGET, message);
    }

    public UUID getId() {
        return id;
    }

    public void setId(UUID id) {
        this.id = id;
    }

    public GoalType getGoalType() {
        return goalType;
    }

    public void setGoalType(GoalType goalType) {
        this.goalType = goalType;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public BigDecimal getTargetValue() {
        return targetValue;
    }

    public void setTargetValue(BigDecimal targetValue) {
        this.targetValue = targetValue;
    }

    public GoalUnit getUnit() {
        return unit;
    }

    public void setUnit(GoalUnit unit) {
        this.unit = unit;
    }

    public BigDecimal getBaselineValue() {
        return baselineValue;
    }

    public void setBaselineValue(BigDecimal baselineValue) {
        this.baselineValue = baselineValue;
    }

    public LocalDate getTargetDate() {
        return targetDate;
    }

    public void setTargetDate(LocalDate targetDate) {
        this.targetDate = targetDate;
    }

    public GoalStatus getStatus() {
        return status;
    }

    public void setStatus(GoalStatus status) {
        this.status = status;
    }

    public Integer getPriority() {
        return priority;
    }

    public void setPriority(Integer priority) {
        this.priority = priority;
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
