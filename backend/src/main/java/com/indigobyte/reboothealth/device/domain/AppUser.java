package com.indigobyte.reboothealth.device.domain;

import java.time.Instant;
import java.util.UUID;

/**
 * 单用户私有部署中的最小用户边界。
 *
 * <p>M2.5-A 不建设完整账号体系；该实体只为设备、AgentRun 和后续数据隔离提供 userId。</p>
 */
public class AppUser {

    private final UUID id;
    private final String status;
    private final Instant createdAt;
    private Instant updatedAt;

    public AppUser(UUID id, String status, Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.status = status;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    public static AppUser create(Instant now) {
        return new AppUser(UUID.randomUUID(), "ACTIVE", now, now);
    }

    public UUID getId() {
        return id;
    }

    public String getStatus() {
        return status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
