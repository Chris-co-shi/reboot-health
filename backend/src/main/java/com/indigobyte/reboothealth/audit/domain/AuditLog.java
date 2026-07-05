package com.indigobyte.reboothealth.audit.domain;

import java.time.Instant;
import java.util.UUID;

public class AuditLog {

    private UUID id;
    private String actor;
    private String action;
    private String entityType;
    private UUID entityId;
    private String beforeSnapshot;
    private String afterSnapshot;
    private Instant createdAt;

    public AuditLog() {
    }

    public AuditLog(UUID id, String actor, String action, String entityType, UUID entityId,
                    String beforeSnapshot, String afterSnapshot, Instant createdAt) {
        this.id = id;
        this.actor = actor;
        this.action = action;
        this.entityType = entityType;
        this.entityId = entityId;
        this.beforeSnapshot = beforeSnapshot;
        this.afterSnapshot = afterSnapshot;
        this.createdAt = createdAt;
    }

    public UUID getId() {
        return id;
    }

    public String getActor() {
        return actor;
    }

    public String getAction() {
        return action;
    }

    public String getEntityType() {
        return entityType;
    }

    public UUID getEntityId() {
        return entityId;
    }

    public String getBeforeSnapshot() {
        return beforeSnapshot;
    }

    public String getAfterSnapshot() {
        return afterSnapshot;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
