package com.indigobyte.reboothealth.plan.domain;

import java.time.Instant;
import java.util.UUID;

/**
 * 长期计划身份。
 *
 * <p>MVP 只维护一个长期 Plan，具体周期内容由 PlanVersion 表达。</p>
 */
public class Plan {

    private final UUID id;
    private String title;
    private String summary;
    private final Instant createdAt;
    private Instant updatedAt;

    public Plan(UUID id, String title, String summary, Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.title = title;
        this.summary = summary;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    public static Plan create(String title, String summary, Instant now) {
        return new Plan(UUID.randomUUID(), title, summary, now, now);
    }

    public void update(String title, String summary, Instant now) {
        this.title = title;
        this.summary = summary;
        this.updatedAt = now;
    }

    public UUID getId() {
        return id;
    }

    public String getTitle() {
        return title;
    }

    public String getSummary() {
        return summary;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
