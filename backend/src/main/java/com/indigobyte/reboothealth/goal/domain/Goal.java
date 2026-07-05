package com.indigobyte.reboothealth.goal.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.Set;
import java.util.UUID;

/**
 * 目标聚合。
 *
 * <p>目标表达方向和可量化指标，不包含每日训练动作。终态目标不可编辑，未来重新开始时应创建新目标。</p>
 */
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

    /**
     * 修改目标定义。仅 ACTIVE 和 PAUSED 可以编辑，避免完成、取消后的历史语义被改写。
     */
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

    /**
     * 普通状态流转不允许进入 ARCHIVED；归档必须走 archive 并提供原因。
     */
    public void changeStatus(GoalStatus targetStatus, Instant now) {
        assertEditable();
        status.assertCanTransitionTo(targetStatus);
        this.status = targetStatus;
        this.updatedAt = now;
    }

    /**
     * 将目标归档。归档是隐藏保留历史的终态，不删除目标记录。
     */
    public void archive(String archiveReason, Instant now) {
        if (archiveReason == null || archiveReason.isBlank()) {
            throw new DomainException(ErrorCode.VALIDATION_ERROR, "归档原因不能为空");
        }
        status.assertCanArchive();
        this.status = GoalStatus.ARCHIVED;
        this.archiveReason = archiveReason;
        this.updatedAt = now;
        this.archivedAt = now;
    }

    private void assertEditable() {
        if (status == GoalStatus.ARCHIVED) {
            throw new DomainException(ErrorCode.GOAL_ARCHIVED, "已归档的目标不能编辑");
        }
        if (status == GoalStatus.COMPLETED || status == GoalStatus.CANCELLED) {
            throw new DomainException(ErrorCode.GOAL_INVALID_STATUS_TRANSITION, "终态目标不能编辑");
        }
    }

    private static void validateTarget(GoalType goalType, BigDecimal targetValue, GoalUnit unit, BigDecimal baselineValue) {
        if (isNegative(targetValue) || isNegative(baselineValue)) {
            throw invalidTarget("目标值和基线值必须大于或等于 0");
        }
        if (unit == GoalUnit.NONE && (targetValue != null || baselineValue != null)) {
            throw invalidTarget("unit 为 NONE 时目标值和基线值应为空");
        }
        if (unit == GoalUnit.NONE && goalType != GoalType.OTHER) {
            throw invalidTarget("只有 OTHER 目标可以使用 NONE 单位");
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
            case SWIMMING -> Set.of(GoalUnit.METERS, GoalUnit.LAPS, GoalUnit.MINUTES, GoalUnit.SECONDS);
            case SLEEP -> Set.of(GoalUnit.MINUTES, GoalUnit.MINUTES_PER_DAY);
            case AEROBIC_CAPACITY, BASKETBALL_CONDITIONING -> Set.of(
                    GoalUnit.MINUTES, GoalUnit.SECONDS, GoalUnit.SCORE, GoalUnit.PERCENT
            );
            case STRENGTH -> Set.of(GoalUnit.REPETITIONS, GoalUnit.SECONDS, GoalUnit.SCORE, GoalUnit.PERCENT);
            case OTHER -> Set.of(GoalUnit.NONE, GoalUnit.KG, GoalUnit.CM, GoalUnit.SESSIONS_PER_WEEK,
                    GoalUnit.MINUTES, GoalUnit.MINUTES_PER_DAY, GoalUnit.METERS, GoalUnit.LAPS,
                    GoalUnit.REPETITIONS, GoalUnit.SECONDS, GoalUnit.SCORE, GoalUnit.PERCENT);
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

    public GoalType getGoalType() {
        return goalType;
    }

    public String getTitle() {
        return title;
    }

    public BigDecimal getTargetValue() {
        return targetValue;
    }

    public GoalUnit getUnit() {
        return unit;
    }

    public BigDecimal getBaselineValue() {
        return baselineValue;
    }

    public LocalDate getTargetDate() {
        return targetDate;
    }

    public GoalStatus getStatus() {
        return status;
    }

    public Integer getPriority() {
        return priority;
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
