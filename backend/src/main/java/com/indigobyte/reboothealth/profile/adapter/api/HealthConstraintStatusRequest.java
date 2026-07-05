package com.indigobyte.reboothealth.profile.adapter.api;

import com.indigobyte.reboothealth.profile.domain.ConstraintStatus;
import jakarta.validation.constraints.NotNull;

/**
 * 健康约束状态变更请求对象。
 *
 * <p>用于 PATCH /api/v1/health-constraints/{id}/status 接口，只允许传入目标状态。</p>
 *
 * @param status 目标状态，不能为 null
 */
public record HealthConstraintStatusRequest(@NotNull ConstraintStatus status) {
}
