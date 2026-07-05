package com.indigobyte.reboothealth.profile.domain;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.Objects;
import java.util.UUID;

/**
 * 个人健康档案聚合。
 *
 * <p>该聚合只保存相对稳定的基础信息和计划启动基线体重，不保存实时体重，避免与后续身体指标记录形成两个事实来源。</p>
 */
public class UserProfile {

    private UUID id;
    private String displayName;
    private Sex sex;
    private LocalDate birthDate;
    private BigDecimal heightCm;
    private BigDecimal baselineWeightKg;
    private String timezone;
    private Instant createdAt;
    private Instant updatedAt;

    public UserProfile(UUID id, String displayName, Sex sex, LocalDate birthDate, BigDecimal heightCm,
                       BigDecimal baselineWeightKg, String timezone, Instant createdAt, Instant updatedAt) {
        this.id = id;
        this.displayName = displayName;
        this.sex = sex;
        this.birthDate = birthDate;
        this.heightCm = heightCm;
        this.baselineWeightKg = baselineWeightKg;
        this.timezone = timezone;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
    }

    public static UserProfile create(String displayName, Sex sex, LocalDate birthDate, BigDecimal heightCm,
                                     BigDecimal baselineWeightKg, String timezone, Instant now) {
        return new UserProfile(UUID.randomUUID(), displayName, sex, birthDate, heightCm, baselineWeightKg, timezone, now, now);
    }

    public boolean hasSameBusinessContent(UserProfile other) {
        return Objects.equals(displayName, other.displayName)
                && sex == other.sex
                && Objects.equals(birthDate, other.birthDate)
                && sameNumber(heightCm, other.heightCm)
                && sameNumber(baselineWeightKg, other.baselineWeightKg)
                && Objects.equals(timezone, other.timezone);
    }

    public void updateFrom(UserProfile requested, Instant now) {
        this.displayName = requested.displayName;
        this.sex = requested.sex;
        this.birthDate = requested.birthDate;
        this.heightCm = requested.heightCm;
        this.baselineWeightKg = requested.baselineWeightKg;
        this.timezone = requested.timezone;
        this.updatedAt = now;
    }

    private static boolean sameNumber(BigDecimal left, BigDecimal right) {
        if (left == null || right == null) {
            return left == right;
        }
        return left.compareTo(right) == 0;
    }

    public UUID getId() {
        return id;
    }

    public String getDisplayName() {
        return displayName;
    }

    public Sex getSex() {
        return sex;
    }

    public LocalDate getBirthDate() {
        return birthDate;
    }

    public BigDecimal getHeightCm() {
        return heightCm;
    }

    public BigDecimal getBaselineWeightKg() {
        return baselineWeightKg;
    }

    public String getTimezone() {
        return timezone;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
