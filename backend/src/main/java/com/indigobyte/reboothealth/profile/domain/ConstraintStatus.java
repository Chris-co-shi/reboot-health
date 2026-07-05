package com.indigobyte.reboothealth.profile.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;

/**
 * 健康约束状态。
 *
 * <p>普通状态变更不包含归档；归档必须走专用接口并写入原因，避免绕过归档审计。</p>
 */
public enum ConstraintStatus {
    ACTIVE,
    INACTIVE,
    RESOLVED,
    ARCHIVED;

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

    public void assertCanArchive() {
        boolean allowed = switch (this) {
            case ACTIVE, INACTIVE, RESOLVED -> true;
            case ARCHIVED -> false;
        };
        if (!allowed) {
            throw invalidTransition(ARCHIVED);
        }
    }

    private DomainException invalidTransition(ConstraintStatus target) {
        return new DomainException(
                ErrorCode.HEALTH_CONSTRAINT_INVALID_STATUS_TRANSITION,
                "健康约束状态不允许从 " + this + " 变更为 " + target
        );
    }
}
