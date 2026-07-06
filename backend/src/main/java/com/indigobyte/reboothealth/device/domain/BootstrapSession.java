package com.indigobyte.reboothealth.device.domain;

import java.time.Instant;
import java.util.UUID;

/**
 * 首台可信设备初始化会话。
 *
 * <p>只保存 code 摘要；明文 code 只在 CLI 生成时展示一次。</p>
 */
public class BootstrapSession {

    private final UUID id;
    private final String codeHash;
    private BootstrapStatus status;
    private final Instant expiresAt;
    private Instant consumedAt;
    private Instant revokedAt;
    private int failureCount;
    private final Instant createdAt;
    private Instant updatedAt;

    public BootstrapSession(UUID id, String codeHash, BootstrapStatus status, Instant expiresAt,
                            Instant consumedAt, Instant revokedAt, int failureCount,
                            Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.codeHash = codeHash;
        this.status = status;
        this.expiresAt = expiresAt;
        this.consumedAt = consumedAt;
        this.revokedAt = revokedAt;
        this.failureCount = failureCount;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    public static BootstrapSession create(String codeHash, Instant expiresAt, Instant now) {
        return new BootstrapSession(UUID.randomUUID(), codeHash, BootstrapStatus.CREATED, expiresAt,
                null, null, 0, now, now);
    }

    public boolean isUsable(Instant now) {
        return status == BootstrapStatus.CREATED && expiresAt.isAfter(now);
    }

    public void markConsumed(Instant now) {
        this.status = BootstrapStatus.CONSUMED;
        this.consumedAt = now;
        this.updatedAt = now;
    }

    public void markExpired(Instant now) {
        this.status = BootstrapStatus.EXPIRED;
        this.updatedAt = now;
    }

    /**
     * 达到失败次数上限后撤销当前 bootstrap code。
     */
    public void revoke(Instant now) {
        this.status = BootstrapStatus.REVOKED;
        this.revokedAt = now;
        this.updatedAt = now;
    }

    public void recordFailure(Instant now) {
        this.failureCount += 1;
        this.updatedAt = now;
    }

    public UUID getId() {
        return id;
    }

    public String getCodeHash() {
        return codeHash;
    }

    public BootstrapStatus getStatus() {
        return status;
    }

    public Instant getExpiresAt() {
        return expiresAt;
    }

    public Instant getConsumedAt() {
        return consumedAt;
    }

    public Instant getRevokedAt() {
        return revokedAt;
    }

    public int getFailureCount() {
        return failureCount;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
