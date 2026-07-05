package com.indigobyte.reboothealth.plan.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

/**
 * 计划周期内的一天。
 *
 * <p>可确认草案必须恰好包含 7 个连续 PlanDay；休息日允许没有 PlanItem。</p>
 */
public class PlanDay {

    private final UUID id;
    private final UUID versionId;
    private LocalDate dayDate;
    private String title;
    private String note;
    private int sortOrder;
    private final Instant createdAt;
    private Instant updatedAt;

    public PlanDay(UUID id, UUID versionId, LocalDate dayDate, String title, String note,
                   int sortOrder, Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.versionId = versionId;
        this.dayDate = dayDate;
        this.title = title;
        this.note = note;
        this.sortOrder = sortOrder;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
        validate();
    }

    public static PlanDay create(UUID versionId, LocalDate dayDate, String title, String note, int sortOrder, Instant now) {
        return new PlanDay(UUID.randomUUID(), versionId, dayDate, title, note, sortOrder, now, now);
    }

    public void update(LocalDate dayDate, String title, String note, int sortOrder, Instant now) {
        this.dayDate = dayDate;
        this.title = title;
        this.note = note;
        this.sortOrder = sortOrder;
        this.updatedAt = now;
        validate();
    }

    private void validate() {
        if (dayDate == null || title == null || title.isBlank() || sortOrder < 1 || sortOrder > 7) {
            throw new DomainException(ErrorCode.VALIDATION_ERROR, "计划日日期、标题和顺序必须有效");
        }
    }

    public UUID getId() {
        return id;
    }

    public UUID getVersionId() {
        return versionId;
    }

    public LocalDate getDayDate() {
        return dayDate;
    }

    public String getTitle() {
        return title;
    }

    public String getNote() {
        return note;
    }

    public int getSortOrder() {
        return sortOrder;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
