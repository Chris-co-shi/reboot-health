package com.indigobyte.reboothealth.profile.domain;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

/**
 * 健康约束聚合。
 *
 * <p>约束由用户手动维护，后续规则引擎和 AI 只能读取当前有效约束，不能删除或自动停用约束。</p>
 */
public class HealthConstraint {

    private UUID id;
    private ConstraintType constraintType;
    private BodyRegion bodyRegion;
    private ConstraintSeverity severity;
    private String title;
    private String description;
    private ConstraintSourceType sourceType;
    private String sourceNote;
    private ConstraintStatus status;
    private LocalDate effectiveFrom;
    private LocalDate effectiveTo;
    private String archiveReason;
    private Instant createdAt;
    private Instant updatedAt;
    private Instant archivedAt;

    public HealthConstraint(UUID id, ConstraintType constraintType, BodyRegion bodyRegion, ConstraintSeverity severity,
                            String title, String description, ConstraintSourceType sourceType, String sourceNote,
                            ConstraintStatus status, LocalDate effectiveFrom, LocalDate effectiveTo,
                            String archiveReason, Instant createdAt, Instant updatedAt, Instant archivedAt) {
        this.id = id;
        this.constraintType = constraintType;
        this.bodyRegion = bodyRegion;
        this.severity = severity;
        this.title = title;
        this.description = description;
        this.sourceType = sourceType;
        this.sourceNote = sourceNote;
        this.status = status;
        this.effectiveFrom = effectiveFrom;
        this.effectiveTo = effectiveTo;
        this.archiveReason = archiveReason;
        this.createdAt = createdAt;
        this.updatedAt = updatedAt;
        this.archivedAt = archivedAt;
    }

    /**
     * 创建新的健康约束。
     *
     * <p>新建的约束默认为 ACTIVE 状态，归档相关字段为 null。</p>
     *
     * @param constraintType 约束类型
     * @param bodyRegion 身体部位
     * @param severity 严重程度
     * @param title 约束标题
     * @param description 详细描述
     * @param sourceType 来源类型
     * @param sourceNote 来源备注或说明
     * @param effectiveFrom 生效开始日期
     * @param effectiveTo 生效结束日期，可为 null 表示长期有效
     * @param now 当前时间戳
     * @return 新建的健康约束对象，ID 自动生成
     * @throws DomainException 如果结束日期早于开始日期
     */
    public static HealthConstraint create(ConstraintType constraintType, BodyRegion bodyRegion,
                                          ConstraintSeverity severity, String title, String description,
                                          ConstraintSourceType sourceType, String sourceNote,
                                          LocalDate effectiveFrom, LocalDate effectiveTo, Instant now) {
        assertValidDateRange(effectiveFrom, effectiveTo);
        return new HealthConstraint(UUID.randomUUID(), constraintType, bodyRegion, severity, title, description,
                sourceType, sourceNote, ConstraintStatus.ACTIVE, effectiveFrom, effectiveTo, null, now, now, null);
    }

    /**
     * 修改普通业务字段。
     *
     * <p>已归档约束不能编辑，防止历史约束被无痕改写。日期范围也会进行合法性校验。</p>
     *
     * @param constraintType 约束类型
     * @param bodyRegion 身体部位
     * @param severity 严重程度
     * @param title 约束标题
     * @param description 详细描述
     * @param sourceType 来源类型
     * @param sourceNote 来源备注或说明
     * @param effectiveFrom 生效开始日期
     * @param effectiveTo 生效结束日期
     * @param now 当前时间戳，用于更新 updatedAt
     * @throws DomainException 如果约束已归档或日期范围不合法
     */
    public void update(ConstraintType constraintType, BodyRegion bodyRegion, ConstraintSeverity severity,
                       String title, String description, ConstraintSourceType sourceType, String sourceNote,
                       LocalDate effectiveFrom, LocalDate effectiveTo, Instant now) {
        assertEditable();
        assertValidDateRange(effectiveFrom, effectiveTo);
        this.constraintType = constraintType;
        this.bodyRegion = bodyRegion;
        this.severity = severity;
        this.title = title;
        this.description = description;
        this.sourceType = sourceType;
        this.sourceNote = sourceNote;
        this.effectiveFrom = effectiveFrom;
        this.effectiveTo = effectiveTo;
        this.updatedAt = now;
    }

    /**
     * 普通状态流转。
     *
     * <p>不允许直接进入 ARCHIVED 状态；归档必须走 archive 方法并提供原因。已归档约束不能变更状态。</p>
     *
     * @param targetStatus 目标状态
     * @param now 当前时间戳，用于更新 updatedAt
     * @throws DomainException 如果约束已归档或状态转换不合法
     */
    public void changeStatus(ConstraintStatus targetStatus, Instant now) {
        assertEditable();
        status.assertCanTransitionTo(targetStatus);
        this.status = targetStatus;
        this.updatedAt = now;
    }

    /**
     * 将约束归档。
     *
     * <p>归档是隐藏保留历史的终态操作，必须提供归档原因并记录归档时间。归档后的约束不能再次编辑或变更状态。</p>
     *
     * @param archiveReason 归档原因，不能为空
     * @param now 当前时间戳，用于更新 updatedAt 和 archivedAt
     * @throws DomainException 如果归档原因为空、约束已归档或状态不允许归档
     */
    public void archive(String archiveReason, Instant now) {
        if (archiveReason == null || archiveReason.isBlank()) {
            throw new DomainException(ErrorCode.VALIDATION_ERROR, "归档原因不能为空");
        }
        status.assertCanArchive();
        this.status = ConstraintStatus.ARCHIVED;
        this.archiveReason = archiveReason;
        this.updatedAt = now;
        this.archivedAt = now;
    }

    /**
     * 断言约束是否可编辑。
     *
     * @throws DomainException 如果约束已归档
     */
    private void assertEditable() {
        if (status == ConstraintStatus.ARCHIVED) {
            throw new DomainException(ErrorCode.HEALTH_CONSTRAINT_ARCHIVED, "已归档的健康约束不能编辑");
        }
    }

    /**
     * 验证日期范围的合法性。
     *
     * @param effectiveFrom 生效开始日期
     * @param effectiveTo 生效结束日期
     * @throws DomainException 如果结束日期早于开始日期
     */
    private static void assertValidDateRange(LocalDate effectiveFrom, LocalDate effectiveTo) {
        if (effectiveFrom != null && effectiveTo != null && effectiveTo.isBefore(effectiveFrom)) {
            throw new DomainException(
                    ErrorCode.HEALTH_CONSTRAINT_INVALID_DATE_RANGE,
                    "健康约束结束日期不能早于开始日期"
            );
        }
    }

    /**
     * 获取约束唯一标识符。
     *
     * @return UUID 格式的约束 ID
     */
    public UUID getId() {
        return id;
    }

    /**
     * 获取约束类型。
     *
     * @return 约束类型枚举值
     */
    public ConstraintType getConstraintType() {
        return constraintType;
    }

    /**
     * 获取受影响的身体部位。
     *
     * @return 身体部位枚举值
     */
    public BodyRegion getBodyRegion() {
        return bodyRegion;
    }

    /**
     * 获取约束严重程度。
     *
     * @return 严重程度枚举值
     */
    public ConstraintSeverity getSeverity() {
        return severity;
    }

    /**
     * 获取约束标题。
     *
     * @return 约束的简短标题
     */
    public String getTitle() {
        return title;
    }

    /**
     * 获取约束详细描述。
     *
     * @return 约束的详细描述信息
     */
    public String getDescription() {
        return description;
    }

    /**
     * 获取约束来源类型。
     *
     * @return 来源类型枚举值
     */
    public ConstraintSourceType getSourceType() {
        return sourceType;
    }

    /**
     * 获取来源备注或说明。
     *
     * @return 来源相关的补充说明
     */
    public String getSourceNote() {
        return sourceNote;
    }

    /**
     * 获取约束当前状态。
     *
     * @return 约束状态枚举值
     */
    public ConstraintStatus getStatus() {
        return status;
    }

    /**
     * 获取生效开始日期。
     *
     * @return 生效开始日期，可能为 null
     */
    public LocalDate getEffectiveFrom() {
        return effectiveFrom;
    }

    /**
     * 获取生效结束日期。
     *
     * @return 生效结束日期，null 表示长期有效
     */
    public LocalDate getEffectiveTo() {
        return effectiveTo;
    }

    /**
     * 获取归档原因。
     *
     * @return 归档时填写的原因说明，未归档时为 null
     */
    public String getArchiveReason() {
        return archiveReason;
    }

    /**
     * 获取约束创建时间。
     *
     * @return 创建时间戳
     */
    public Instant getCreatedAt() {
        return createdAt;
    }

    /**
     * 获取约束最后更新时间。
     *
     * @return 最后更新时间戳
     */
    public Instant getUpdatedAt() {
        return updatedAt;
    }

    /**
     * 获取约束归档时间。
     *
     * @return 归档时间戳，未归档时为 null
     */
    public Instant getArchivedAt() {
        return archivedAt;
    }
}
