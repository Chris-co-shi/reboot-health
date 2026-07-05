package com.indigobyte.reboothealth.plan.domain;

/**
 * 人工计划条目的训练类型。
 *
 * <p>M2B 只保存足够支持人工计划的分类，不建立复杂动作库。</p>
 */
public enum PlanItemType {
    BODYWEIGHT,
    GYM,
    SWIMMING,
    BASKETBALL,
    RECOVERY,
    REST,
    OTHER
}
