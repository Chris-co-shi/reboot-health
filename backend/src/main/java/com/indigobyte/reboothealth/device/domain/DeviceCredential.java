package com.indigobyte.reboothealth.device.domain;

import java.time.Instant;
import java.util.UUID;

/**
 * 设备凭据摘要。
 *
 * <p>服务端只保存 access token 和 refresh credential 的摘要，不保存任何明文凭据。</p>
 */
public class DeviceCredential {

    private final UUID id;
    private final UUID deviceId;
    private String accessTokenHash;
    private Instant accessTokenExpiresAt;
    private String refreshTokenHash;
    private Instant refreshTokenExpiresAt;
    private Instant refreshTokenRotatedAt;
    private Instant revokedAt;
    private final Instant createdAt;
    private Instant updatedAt;

    public DeviceCredential(UUID id, UUID deviceId, String accessTokenHash, Instant accessTokenExpiresAt,
                            String refreshTokenHash, Instant refreshTokenExpiresAt,
                            Instant refreshTokenRotatedAt, Instant revokedAt,
                            Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.deviceId = deviceId;
        this.accessTokenHash = accessTokenHash;
        this.accessTokenExpiresAt = accessTokenExpiresAt;
        this.refreshTokenHash = refreshTokenHash;
        this.refreshTokenExpiresAt = refreshTokenExpiresAt;
        this.refreshTokenRotatedAt = refreshTokenRotatedAt;
        this.revokedAt = revokedAt;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    public static DeviceCredential create(UUID deviceId, TokenPair tokenPair, Instant now) {
        return new DeviceCredential(UUID.randomUUID(), deviceId, tokenPair.accessTokenHash(),
                tokenPair.accessTokenExpiresAt(), tokenPair.refreshTokenHash(),
                tokenPair.refreshTokenExpiresAt(), null, null, now, now);
    }

    public boolean isAccessTokenValid(Instant now) {
        return revokedAt == null && accessTokenExpiresAt.isAfter(now);
    }

    public boolean isRefreshTokenValid(Instant now) {
        return revokedAt == null && refreshTokenExpiresAt.isAfter(now);
    }

    public void rotate(TokenPair tokenPair, Instant now) {
        this.accessTokenHash = tokenPair.accessTokenHash();
        this.accessTokenExpiresAt = tokenPair.accessTokenExpiresAt();
        this.refreshTokenHash = tokenPair.refreshTokenHash();
        this.refreshTokenExpiresAt = tokenPair.refreshTokenExpiresAt();
        this.refreshTokenRotatedAt = now;
        this.updatedAt = now;
    }

    public void revoke(Instant now) {
        this.revokedAt = now;
        this.updatedAt = now;
    }

    public UUID getId() {
        return id;
    }

    public UUID getDeviceId() {
        return deviceId;
    }

    public String getAccessTokenHash() {
        return accessTokenHash;
    }

    public Instant getAccessTokenExpiresAt() {
        return accessTokenExpiresAt;
    }

    public String getRefreshTokenHash() {
        return refreshTokenHash;
    }

    public Instant getRefreshTokenExpiresAt() {
        return refreshTokenExpiresAt;
    }

    public Instant getRefreshTokenRotatedAt() {
        return refreshTokenRotatedAt;
    }

    public Instant getRevokedAt() {
        return revokedAt;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
