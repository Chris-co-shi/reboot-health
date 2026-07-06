package com.indigobyte.reboothealth.agent.domain;

import java.time.Instant;
import java.util.UUID;

/**
 * Agent 运行记录聚合。
 *
 * <p>Java 后端是 AgentRun 状态权威；Python 只能返回结构化候选结果，不能直接标记最终业务状态。</p>
 */
public class AgentRun {

    private final UUID id;
    private final UUID userId;
    private final UUID deviceId;
    private final UUID sessionId;
    private final AgentTriggerType triggerType;
    private AgentRunStatus status;
    private final String inputSummary;
    private String structuredOutput;
    private String validationResult;
    private String failureCode;
    private String failureMessage;
    private final Instant createdAt;
    private Instant startedAt;
    private Instant completedAt;
    private Instant updatedAt;

    public AgentRun(UUID id, UUID userId, UUID deviceId, UUID sessionId, AgentTriggerType triggerType,
                    AgentRunStatus status, String inputSummary, String structuredOutput,
                    String validationResult, String failureCode, String failureMessage,
                    Instant createdAt, Instant startedAt, Instant completedAt, Instant updatedAt) {
        this.id = id;
        this.userId = userId;
        this.deviceId = deviceId;
        this.sessionId = sessionId;
        this.triggerType = triggerType;
        this.status = status;
        this.inputSummary = inputSummary;
        this.structuredOutput = structuredOutput;
        this.validationResult = validationResult;
        this.failureCode = failureCode;
        this.failureMessage = failureMessage;
        this.createdAt = createdAt;
        this.startedAt = startedAt;
        this.completedAt = completedAt;
        this.updatedAt = updatedAt;
    }

    public static AgentRun create(UUID userId, UUID deviceId, UUID sessionId,
                                  AgentTriggerType triggerType, String inputSummary, Instant now) {
        return new AgentRun(UUID.randomUUID(), userId, deviceId, sessionId, triggerType, AgentRunStatus.CREATED,
                inputSummary, null, null, null, null, now, null, null, now);
    }

    public void markRunning(Instant now) {
        this.status = AgentRunStatus.RUNNING;
        this.startedAt = now;
        this.updatedAt = now;
    }

    public void markValidating(Instant now) {
        this.status = AgentRunStatus.VALIDATING;
        this.updatedAt = now;
    }

    public void markReady(String structuredOutput, String validationResult, Instant now) {
        this.status = AgentRunStatus.READY_FOR_USER_REVIEW;
        this.structuredOutput = structuredOutput;
        this.validationResult = validationResult;
        this.failureCode = null;
        this.failureMessage = null;
        this.completedAt = now;
        this.updatedAt = now;
    }

    public void markFailed(String failureCode, String failureMessage, Instant now) {
        this.status = AgentRunStatus.FAILED;
        this.failureCode = failureCode;
        this.failureMessage = failureMessage;
        this.completedAt = now;
        this.updatedAt = now;
    }

    public void markExpired(String failureMessage, Instant now) {
        this.status = AgentRunStatus.EXPIRED;
        this.failureCode = AgentRunStatus.EXPIRED.name();
        this.failureMessage = failureMessage;
        this.completedAt = now;
        this.updatedAt = now;
    }

    public UUID getId() {
        return id;
    }

    public UUID getUserId() {
        return userId;
    }

    public UUID getDeviceId() {
        return deviceId;
    }

    public UUID getSessionId() {
        return sessionId;
    }

    public AgentTriggerType getTriggerType() {
        return triggerType;
    }

    public AgentRunStatus getStatus() {
        return status;
    }

    public String getInputSummary() {
        return inputSummary;
    }

    public String getStructuredOutput() {
        return structuredOutput;
    }

    public String getValidationResult() {
        return validationResult;
    }

    public String getFailureCode() {
        return failureCode;
    }

    public String getFailureMessage() {
        return failureMessage;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getStartedAt() {
        return startedAt;
    }

    public Instant getCompletedAt() {
        return completedAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
