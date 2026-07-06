package com.indigobyte.reboothealth.agent.domain;

/**
 * AgentRun 生命周期状态。
 */
public enum AgentRunStatus {
    CREATED,
    RUNNING,
    VALIDATING,
    READY_FOR_USER_REVIEW,
    FAILED,
    CANCELLED,
    EXPIRED
}
