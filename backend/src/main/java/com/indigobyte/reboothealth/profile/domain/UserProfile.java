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

    /**
     * 创建新的个人健康档案。
     *
     * @param displayName 显示名称
     * @param sex 性别
     * @param birthDate 出生日期
     * @param heightCm 身高（厘米）
     * @param baselineWeightKg 基线体重（千克），用于计划启动时的初始参考
     * @param timezone 时区标识
     * @param now 当前时间戳
     * @return 新建的个人档案对象，ID 自动生成
     */
    public static UserProfile create(String displayName, Sex sex, LocalDate birthDate, BigDecimal heightCm,
                                     BigDecimal baselineWeightKg, String timezone, Instant now) {
        return new UserProfile(UUID.randomUUID(), displayName, sex, birthDate, heightCm, baselineWeightKg, timezone, now, now);
    }

    /**
     * 判断另一个档案是否与当前档案具有相同的业务内容。
     *
     * <p>用于检测档案更新时是否需要实际写入数据库，避免无意义的更新操作。</p>
     *
     * @param other 要比较的另一个档案对象
     * @return 如果所有业务字段相同返回 true，否则返回 false
     */
    public boolean hasSameBusinessContent(UserProfile other) {
        return Objects.equals(displayName, other.displayName)
                && sex == other.sex
                && Objects.equals(birthDate, other.birthDate)
                && sameNumber(heightCm, other.heightCm)
                && sameNumber(baselineWeightKg, other.baselineWeightKg)
                && Objects.equals(timezone, other.timezone);
    }

    /**
     * 从另一个档案对象更新当前档案的业务字段。
     *
     * <p>复制所有可编辑字段并更新时间戳，用于持久化层保存前的数据同步。</p>
     *
     * @param requested 包含新数据的档案对象
     * @param now 当前时间戳，用于更新 updatedAt
     */
    public void updateFrom(UserProfile requested, Instant now) {
        this.displayName = requested.displayName;
        this.sex = requested.sex;
        this.birthDate = requested.birthDate;
        this.heightCm = requested.heightCm;
        this.baselineWeightKg = requested.baselineWeightKg;
        this.timezone = requested.timezone;
        this.updatedAt = now;
    }

    /**
     * 比较两个 BigDecimal 值是否相等，处理 null 情况。
     *
     * @param left 左侧值
     * @param right 右侧值
     * @return 如果两者相等（包括同为 null）返回 true
     */
    private static boolean sameNumber(BigDecimal left, BigDecimal right) {
        if (left == null || right == null) {
            return left == right;
        }
        return left.compareTo(right) == 0;
    }

    /**
     * 获取档案唯一标识符。
     *
     * @return UUID 格式的档案 ID
     */
    public UUID getId() {
        return id;
    }

    /**
     * 获取用户显示名称。
     *
     * @return 用户的显示名称
     */
    public String getDisplayName() {
        return displayName;
    }

    /**
     * 获取用户性别。
     *
     * @return 性别枚举值
     */
    public Sex getSex() {
        return sex;
    }

    /**
     * 获取用户出生日期。
     *
     * @return 出生日期，可能为 null
     */
    public LocalDate getBirthDate() {
        return birthDate;
    }

    /**
     * 获取用户身高。
     *
     * @return 身高（厘米），可能为 null
     */
    public BigDecimal getHeightCm() {
        return heightCm;
    }

    /**
     * 获取基线体重。
     *
     * <p>这是计划启动时的参考体重，不是实时体重。</p>
     *
     * @return 基线体重（千克），可能为 null
     */
    public BigDecimal getBaselineWeightKg() {
        return baselineWeightKg;
    }

    /**
     * 获取用户时区。
     *
     * @return 时区标识，如 "Asia/Shanghai"
     */
    public String getTimezone() {
        return timezone;
    }

    /**
     * 获取档案创建时间。
     *
     * @return 创建时间戳
     */
    public Instant getCreatedAt() {
        return createdAt;
    }

    /**
     * 获取档案最后更新时间。
     *
     * @return 最后更新时间戳
     */
    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
