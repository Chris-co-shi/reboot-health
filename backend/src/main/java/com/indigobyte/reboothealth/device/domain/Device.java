package com.indigobyte.reboothealth.device.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.time.Instant;
import java.util.UUID;

/**
 * 已登记设备聚合。
 *
 * <p>每台设备独立撤销，撤销后不得继续刷新凭据；首台设备使用 TRUSTED_PRIMARY 标记。</p>
 */
public class Device {

    private final UUID id;
    private final UUID userId;
    private final String deviceName;
    private final DevicePlatform platform;
    private DeviceStatus status;
    private final DeviceTrustLevel trustLevel;
    private final Instant createdAt;
    private Instant lastSeenAt;
    private Instant revokedAt;
    private Instant updatedAt;

    public Device(UUID id, UUID userId, String deviceName, DevicePlatform platform, DeviceStatus status,
                  DeviceTrustLevel trustLevel, Instant createdAt, Instant lastSeenAt,
                  Instant revokedAt, Instant updatedAt) {
        this.id = id;
        this.userId = userId;
        this.deviceName = deviceName;
        this.platform = platform;
        this.status = status;
        this.trustLevel = trustLevel;
        this.createdAt = createdAt;
        this.lastSeenAt = lastSeenAt;
        this.revokedAt = revokedAt;
        this.updatedAt = updatedAt;
    }

    public static Device trustedPrimary(UUID userId, String deviceName, DevicePlatform platform, Instant now) {
        return new Device(UUID.randomUUID(), userId, normalizeName(deviceName), platform, DeviceStatus.ACTIVE,
                DeviceTrustLevel.TRUSTED_PRIMARY, now, now, null, now);
    }

    public static Device trusted(UUID userId, String deviceName, DevicePlatform platform, Instant now) {
        return new Device(UUID.randomUUID(), userId, normalizeName(deviceName), platform, DeviceStatus.ACTIVE,
                DeviceTrustLevel.TRUSTED, now, now, null, now);
    }

    public void markSeen(Instant now) {
        ensureActive();
        this.lastSeenAt = now;
        this.updatedAt = now;
    }

    public void revoke(Instant now) {
        ensureActive();
        this.status = DeviceStatus.REVOKED;
        this.revokedAt = now;
        this.updatedAt = now;
    }

    public void ensureActive() {
        if (status != DeviceStatus.ACTIVE) {
            throw new DomainException(ErrorCode.DEVICE_REVOKED, "设备已撤销");
        }
    }

    private static String normalizeName(String value) {
        if (value == null || value.isBlank()) {
            return "未命名设备";
        }
        return value.trim();
    }

    public UUID getId() {
        return id;
    }

    public UUID getUserId() {
        return userId;
    }

    public String getDeviceName() {
        return deviceName;
    }

    public DevicePlatform getPlatform() {
        return platform;
    }

    public DeviceStatus getStatus() {
        return status;
    }

    public DeviceTrustLevel getTrustLevel() {
        return trustLevel;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getLastSeenAt() {
        return lastSeenAt;
    }

    public Instant getRevokedAt() {
        return revokedAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
