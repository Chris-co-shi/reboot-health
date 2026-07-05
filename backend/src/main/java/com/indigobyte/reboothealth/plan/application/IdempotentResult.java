package com.indigobyte.reboothealth.plan.application;

/**
 * 幂等 POST 的应用层返回值。
 */
public record IdempotentResult<T>(T body, int responseStatus, boolean replayed) {
}
