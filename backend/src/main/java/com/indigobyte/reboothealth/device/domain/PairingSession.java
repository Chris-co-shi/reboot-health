package com.indigobyte.reboothealth.device.domain;

import java.time.Instant;
import java.util.UUID;

/**
 * 后续设备配对会话。
 *
 * <p>会话只能由已授权设备创建，并且只能被新设备消费一次。</p>
 */
public class PairingSession {

    private final UUID id;
    private final UUID userId;
    private final UUID createdByDeviceId;
    private final String codeHash;
    private PairingStatus status;
    private final Instant expiresAt;
    private Instant consumedAt;
    private Instant cancelledAt;
    private UUID createdDeviceId;
    private final Instant createdAt;
    private Instant updatedAt;

    public PairingSession(UUID id, UUID userId, UUID createdByDeviceId, String codeHash,
                          PairingStatus status, Instant expiresAt, Instant consumedAt, Instant cancelledAt,
                          UUID createdDeviceId, Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.userId = userId;
        this.createdByDeviceId = createdByDeviceId;
        this.codeHash = codeHash;
        this.status = status;
        this.expiresAt = expiresAt;
        this.consumedAt = consumedAt;
        this.cancelledAt = cancelledAt;
        this.createdDeviceId = createdDeviceId;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    public static PairingSession create(UUID userId, UUID createdByDeviceId, String codeHash,
                                        Instant expiresAt, Instant now) {
        return new PairingSession(UUID.randomUUID(), userId, createdByDeviceId, codeHash,
                PairingStatus.CREATED, expiresAt, null, null, null, now, now);
    }

    public boolean isUsable(Instant now) {
        return status == PairingStatus.CREATED && expiresAt.isAfter(now);
    }

    public void markConsumed(UUID deviceId, Instant now) {
        this.status = PairingStatus.CONSUMED;
        this.createdDeviceId = deviceId;
        this.consumedAt = now;
        this.updatedAt = now;
    }

    public void markExpired(Instant now) {
        this.status = PairingStatus.EXPIRED;
        this.updatedAt = now;
    }

    public UUID getId() {
        return id;
    }

    public UUID getUserId() {
        return userId;
    }

    public UUID getCreatedByDeviceId() {
        return createdByDeviceId;
    }

    public String getCodeHash() {
        return codeHash;
    }

    public PairingStatus getStatus() {
        return status;
    }

    public Instant getExpiresAt() {
        return expiresAt;
    }

    public Instant getConsumedAt() {
        return consumedAt;
    }

    public Instant getCancelledAt() {
        return cancelledAt;
    }

    public UUID getCreatedDeviceId() {
        return createdDeviceId;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
