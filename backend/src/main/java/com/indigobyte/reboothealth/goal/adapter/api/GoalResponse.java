package com.indigobyte.reboothealth.goal.adapter.api;

import com.indigobyte.reboothealth.goal.domain.Goal;
import com.indigobyte.reboothealth.goal.domain.GoalStatus;
import com.indigobyte.reboothealth.goal.domain.GoalType;
import com.indigobyte.reboothealth.goal.domain.GoalUnit;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

public record GoalResponse(
        UUID id,
        GoalType goalType,
        String title,
        BigDecimal targetValue,
        GoalUnit unit,
        BigDecimal baselineValue,
        LocalDate targetDate,
        GoalStatus status,
        Integer priority,
        String archiveReason,
        Instant createdAt,
        Instant updatedAt,
        Instant archivedAt
) {
    public static GoalResponse from(Goal goal) {
        return new GoalResponse(
                goal.getId(),
                goal.getGoalType(),
                goal.getTitle(),
                goal.getTargetValue(),
                goal.getUnit(),
                goal.getBaselineValue(),
                goal.getTargetDate(),
                goal.getStatus(),
                goal.getPriority(),
                goal.getArchiveReason(),
                goal.getCreatedAt(),
                goal.getUpdatedAt(),
                goal.getArchivedAt()
        );
    }
}
