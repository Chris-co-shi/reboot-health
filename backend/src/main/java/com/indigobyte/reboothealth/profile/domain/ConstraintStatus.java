package com.indigobyte.reboothealth.profile.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;

public enum ConstraintStatus {
    ACTIVE,
    INACTIVE,
    RESOLVED,
    ARCHIVED;

    public void assertCanTransitionTo(ConstraintStatus target) {
        boolean allowed = switch (this) {
            case ACTIVE -> target == INACTIVE || target == RESOLVED || target == ARCHIVED;
            case INACTIVE -> target == ACTIVE || target == RESOLVED || target == ARCHIVED;
            case RESOLVED -> target == ARCHIVED;
            case ARCHIVED -> false;
        };
        if (!allowed) {
            throw new DomainException(
                    ErrorCode.HEALTH_CONSTRAINT_INVALID_STATUS_TRANSITION,
                    "健康约束状态不允许从 " + this + " 变更为 " + target
            );
        }
    }
}
