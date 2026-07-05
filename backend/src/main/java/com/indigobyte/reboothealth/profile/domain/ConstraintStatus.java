package com.indigobyte.reboothealth.profile.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;

/**
 * 健康约束状态。
 *
 * <p>普通状态变更不包含归档；归档必须走专用接口并写入原因，避免绕过归档审计。</p>
 */
public enum ConstraintStatus {
    /** 约束处于生效状态，规则引擎和 AI 必须遵守 */
    ACTIVE,
    /** 约束暂时停用，但保留记录以便后续重新启用 */
    INACTIVE,
    /** 约束问题已解决，不再对计划产生影响 */
    RESOLVED,
    /** 约束已归档，作为历史记录保留但不能编辑或重新启用 */
    ARCHIVED;

    /**
     * 断言当前状态是否可以转换到目标状态。
     *
     * <p>允许的状态流转：ACTIVE → INACTIVE/RESOLVED，INACTIVE → ACTIVE/RESOLVED。RESOLVED 和 ARCHIVED 为终态，不允许再次变更。</p>
     *
     * @param target 目标状态
     * @throws DomainException 如果状态转换不合法
     */
    public void assertCanTransitionTo(ConstraintStatus target) {
        boolean allowed = switch (this) {
            case ACTIVE -> target == INACTIVE || target == RESOLVED;
            case INACTIVE -> target == ACTIVE || target == RESOLVED;
            case RESOLVED, ARCHIVED -> false;
        };
        if (!allowed) {
            throw invalidTransition(target);
        }
    }

    /**
     * 断言当前状态是否可以归档。
     *
     * <p>ACTIVE、INACTIVE、RESOLVED 状态的约束可以归档，ARCHIVED 状态不允许重复归档。</p>
     *
     * @throws DomainException 如果当前状态不允许归档
     */
    public void assertCanArchive() {
        boolean allowed = switch (this) {
            case ACTIVE, INACTIVE, RESOLVED -> true;
            case ARCHIVED -> false;
        };
        if (!allowed) {
            throw invalidTransition(ARCHIVED);
        }
    }

    /**
     * 创建非法状态转换异常。
     *
     * @param target 目标状态
     * @return 包含错误码和详细信息的领域异常
     */
    private DomainException invalidTransition(ConstraintStatus target) {
        return new DomainException(
                ErrorCode.HEALTH_CONSTRAINT_INVALID_STATUS_TRANSITION,
                "健康约束状态不允许从 " + this + " 变更为 " + target
        );
    }
}
