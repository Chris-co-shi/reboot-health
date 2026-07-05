package com.indigobyte.reboothealth.profile.domain;

/**
 * 健康约束来源类型枚举。
 *
 * <p>用于标识健康约束信息的来源渠道，便于追溯约束的可靠性和上下文背景。</p>
 */
public enum ConstraintSourceType {
    /** 用户主动报告的健康问题或限制 */
    USER_REPORTED,
    /** 医生或专业医疗人员提供的建议 */
    DOCTOR_ADVICE,
    /** 医学检查报告或诊断证明 */
    MEDICAL_REPORT,
    /** 通过测量或评估获得的数据 */
    MEASUREMENT,
    /** 其他来源 */
    OTHER
}
