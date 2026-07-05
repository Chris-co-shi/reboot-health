package com.indigobyte.reboothealth.profile.domain;

/**
 * 健康约束查询过滤器。
 *
 * <p>用于仓储层查询时指定过滤条件，支持按状态筛选和是否包含已归档约束。</p>
 *
 * @param status 要筛选的状态，为 null 时不过滤状态
 * @param includeArchived 是否在结果中包含已归档的约束
 */
public record HealthConstraintFilter(ConstraintStatus status, boolean includeArchived) {
}
