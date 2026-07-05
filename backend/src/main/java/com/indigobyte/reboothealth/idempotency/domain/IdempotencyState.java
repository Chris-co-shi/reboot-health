package com.indigobyte.reboothealth.idempotency.domain;

/**
 * 幂等记录状态。
 */
public enum IdempotencyState {
    PROCESSING,
    COMPLETED
}
