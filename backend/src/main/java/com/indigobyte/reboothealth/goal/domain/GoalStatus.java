package com.indigobyte.reboothealth.goal.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;

/**
 * 目标状态。
 *
 * <p>完成、取消、归档都是终态；普通状态接口不负责归档，归档必须走专用接口并保留原因。</p>
 */
public enum GoalStatus {
    ACTIVE,
    PAUSED,
    COMPLETED,
    CANCELLED,
    ARCHIVED;

    public void assertCanTransitionTo(GoalStatus target) {
        boolean allowed = switch (this) {
            case ACTIVE -> target == PAUSED || target == COMPLETED || target == CANCELLED;
            case PAUSED -> target == ACTIVE || target == COMPLETED || target == CANCELLED;
            case COMPLETED, CANCELLED, ARCHIVED -> false;
        };
        if (!allowed) {
            throw invalidTransition(target);
        }
    }

    public void assertCanArchive() {
        boolean allowed = switch (this) {
            case ACTIVE, PAUSED, COMPLETED, CANCELLED -> true;
            case ARCHIVED -> false;
        };
        if (!allowed) {
            throw invalidTransition(ARCHIVED);
        }
    }

    private DomainException invalidTransition(GoalStatus target) {
        return new DomainException(
                ErrorCode.GOAL_INVALID_STATUS_TRANSITION,
                "目标状态不允许从 " + this + " 变更为 " + target
        );
    }
}
