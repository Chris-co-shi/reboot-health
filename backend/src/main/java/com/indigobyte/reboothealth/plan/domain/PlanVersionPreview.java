package com.indigobyte.reboothealth.plan.domain;

import java.util.List;

/**
 * 计划版本确认前预览结果。
 *
 * <p>预览聚合计划详情、目标摘要、健康约束上下文和完整性校验结果，前端据此决定是否允许确认。</p>
 */
public record PlanVersionPreview(
        PlanVersionDetail detail,
        List<GoalSummarySnapshot> goals,
        HealthConstraintSnapshot healthConstraints,
        List<String> validationIssues,
        boolean canConfirm
) {
}
