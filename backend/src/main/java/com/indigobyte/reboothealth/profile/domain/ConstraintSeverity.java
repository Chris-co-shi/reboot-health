package com.indigobyte.reboothealth.profile.domain;

/**
 * 健康约束严重程度枚举。
 *
 * <p>用于标识健康约束的严重等级，帮助规则引擎和 AI 在生成计划时采取不同的安全策略。</p>
 */
public enum ConstraintSeverity {
    /**
     * 信息级别，仅作为参考不影响计划生成
     */
    INFO,
    /**
     * 轻度约束，需要轻微注意
     */
    LOW,
    /**
     * 中度约束，需要明显调整计划
     */
    MEDIUM,
    /**
     * 重度约束，必须严格遵守限制
     */
    HIGH,
    /**
     * 危急约束，可能危及生命安全，必须绝对避免相关动作
     */
    CRITICAL
}
