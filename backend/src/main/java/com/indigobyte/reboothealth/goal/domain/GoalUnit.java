package com.indigobyte.reboothealth.goal.domain;

/**
 * 目标计量单位。
 *
 * <p>枚举仅作为明确单位集合，合法的目标类型与单位组合由 Goal 聚合校验。</p>
 */
public enum GoalUnit {
    KG,
    CM,
    SESSIONS_PER_WEEK,
    MINUTES,
    MINUTES_PER_DAY,
    METERS,
    LAPS,
    REPETITIONS,
    SECONDS,
    SCORE,
    PERCENT,
    NONE
}
