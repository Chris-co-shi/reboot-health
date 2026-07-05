package com.indigobyte.reboothealth.idempotency.domain;

import java.time.Instant;
import java.util.UUID;

/**
 * HTTP POST 幂等记录。
 *
 * <p>记录只保存命令指纹和资源定位信息，不保存完整响应体；重放时由业务查询恢复当前资源表示。</p>
 */
public class IdempotencyRecord {

    private final UUID id;
    private final String idempotencyKey;
    private final String operationCode;
    private final String requestHash;
    private IdempotencyState state;
    private String resourceType;
    private UUID resourceId;
    private Integer responseStatus;
    private final Instant createdAt;
    private Instant completedAt;

    public IdempotencyRecord(UUID id, String idempotencyKey, String operationCode, String requestHash,
                             IdempotencyState state, String resourceType, UUID resourceId, Integer responseStatus,
                             Instant createdAt, Instant completedAt) {
        this.id = id;
        this.idempotencyKey = idempotencyKey;
        this.operationCode = operationCode;
        this.requestHash = requestHash;
        this.state = state;
        this.resourceType = resourceType;
        this.resourceId = resourceId;
        this.responseStatus = responseStatus;
        this.createdAt = createdAt;
        this.completedAt = completedAt;
    }

    public static IdempotencyRecord processing(String key, String operationCode, String requestHash, Instant now) {
        return new IdempotencyRecord(UUID.randomUUID(), key, operationCode, requestHash, IdempotencyState.PROCESSING,
                null, null, null, now, null);
    }

    public void complete(String resourceType, UUID resourceId, int responseStatus, Instant now) {
        this.state = IdempotencyState.COMPLETED;
        this.resourceType = resourceType;
        this.resourceId = resourceId;
        this.responseStatus = responseStatus;
        this.completedAt = now;
    }

    public UUID getId() {
        return id;
    }

    public String getIdempotencyKey() {
        return idempotencyKey;
    }

    public String getOperationCode() {
        return operationCode;
    }

    public String getRequestHash() {
        return requestHash;
    }

    public IdempotencyState getState() {
        return state;
    }

    public String getResourceType() {
        return resourceType;
    }

    public UUID getResourceId() {
        return resourceId;
    }

    public Integer getResponseStatus() {
        return responseStatus;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getCompletedAt() {
        return completedAt;
    }
}
