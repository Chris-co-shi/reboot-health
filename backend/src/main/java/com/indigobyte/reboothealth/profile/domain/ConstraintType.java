package com.indigobyte.reboothealth.profile.domain;

/**
 * 健康约束类型枚举。
 *
 * <p>定义系统中支持的健康约束分类，用于规则引擎识别和 AI 生成计划时的安全限制。</p>
 */
public enum ConstraintType {
    /** 高血压及相关心血管约束 */
    HYPERTENSION,
    /** 颈椎活动受限或损伤 */
    CERVICAL_LIMITATION,
    /** 肩颈部位不适或疼痛 */
    SHOULDER_NECK_DISCOMFORT,
    /** 腰部劳损或下背部问题 */
    LOWER_BACK_STRAIN,
    /** 髋关节活动度受限 */
    HIP_MOBILITY_LIMITATION,
    /** 足底筋膜或足部问题 */
    FOOT_SOLE_ISSUE,
    /** 跟腱不适或损伤 */
    ACHILLES_DISCOMFORT,
    /** 禁止执行的特定动作或运动 */
    FORBIDDEN_MOVEMENT,
    /** 训练时需要注意的事项或限制 */
    TRAINING_PRECAUTION,
    /** 其他未分类的约束类型 */
    OTHER
}
