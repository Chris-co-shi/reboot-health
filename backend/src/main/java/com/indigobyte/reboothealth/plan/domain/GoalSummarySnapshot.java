package com.indigobyte.reboothealth.plan.domain;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;

/**
 * 计划确认时保存的目标摘要快照。
 *
 * <p>该快照用于历史计划展示，避免 Goal 后续修改影响已确认版本的上下文。</p>
 */
public record GoalSummarySnapshot(
        UUID goalId,
        String title,
        String goalType,
        String status,
        BigDecimal targetValue,
        String unit,
        BigDecimal baselineValue,
        LocalDate targetDate
) {
}
