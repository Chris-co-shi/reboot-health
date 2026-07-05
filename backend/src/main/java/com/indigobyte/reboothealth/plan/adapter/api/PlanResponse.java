package com.indigobyte.reboothealth.plan.adapter.api;

import com.indigobyte.reboothealth.plan.domain.Plan;
import java.time.Instant;
import java.util.UUID;

/**
 * 长期计划响应 DTO。
 */
public record PlanResponse(UUID id, String title, String summary, Instant createdAt, Instant updatedAt) {

    public static PlanResponse from(Plan plan) {
        return new PlanResponse(plan.getId(), plan.getTitle(), plan.getSummary(), plan.getCreatedAt(), plan.getUpdatedAt());
    }
}
