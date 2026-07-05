package com.indigobyte.reboothealth.plan.domain;

/**
 * 计划版本状态。
 *
 * <p>M2B 不使用 ACTIVE。当前计划由 CONFIRMED 版本的日期范围计算得到，状态只表达版本是否可编辑和是否被替代。</p>
 */
public enum PlanVersionStatus {
    DRAFT,
    CONFIRMED,
    SUPERSEDED,
    CANCELLED
}
