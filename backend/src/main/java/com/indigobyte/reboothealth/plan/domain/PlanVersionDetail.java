package com.indigobyte.reboothealth.plan.domain;

import java.util.List;
import java.util.UUID;

/**
 * 计划版本完整详情。
 *
 * <p>用于 API 返回、确认前完整性校验和幂等重放资源恢复；目标和健康约束字段用于展示版本上下文快照。</p>
 */
public record PlanVersionDetail(
        PlanVersion version,
        List<PlanDayDetail> days,
        List<UUID> goalIds,
        List<GoalSummarySnapshot> goals,
        HealthConstraintSnapshot healthConstraints
) {
}
