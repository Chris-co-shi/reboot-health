package com.indigobyte.reboothealth.goal.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;

public enum GoalStatus {
    ACTIVE,
    PAUSED,
    COMPLETED,
    CANCELLED,
    ARCHIVED;

    public void assertCanTransitionTo(GoalStatus target) {
        boolean allowed = switch (this) {
            case ACTIVE -> target == PAUSED || target == COMPLETED || target == CANCELLED || target == ARCHIVED;
            case PAUSED -> target == ACTIVE || target == COMPLETED || target == CANCELLED || target == ARCHIVED;
            case COMPLETED, CANCELLED -> target == ARCHIVED;
            case ARCHIVED -> false;
        };
        if (!allowed) {
            throw new DomainException(
                    ErrorCode.GOAL_INVALID_STATUS_TRANSITION,
                    "目标状态不允许从 " + this + " 变更为 " + target
            );
        }
    }
}
