package com.indigobyte.reboothealth.idempotency.application;

import com.indigobyte.reboothealth.idempotency.domain.IdempotencyRecord;

/**
 * 幂等请求起始结果。
 */
public record IdempotencyStart(boolean newRequest, IdempotencyRecord existingRecord, String requestHash) {
}
