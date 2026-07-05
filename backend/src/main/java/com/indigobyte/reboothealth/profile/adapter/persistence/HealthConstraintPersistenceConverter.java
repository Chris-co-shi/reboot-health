package com.indigobyte.reboothealth.profile.adapter.persistence;

import com.indigobyte.reboothealth.profile.domain.BodyRegion;
import com.indigobyte.reboothealth.profile.domain.ConstraintSeverity;
import com.indigobyte.reboothealth.profile.domain.ConstraintSourceType;
import com.indigobyte.reboothealth.profile.domain.ConstraintStatus;
import com.indigobyte.reboothealth.profile.domain.ConstraintType;
import com.indigobyte.reboothealth.profile.domain.HealthConstraint;

/**
 * HealthConstraint 聚合与 health_constraint 持久化对象之间的转换器。
 *
 * <p>DO 使用字符串保存枚举，转换器集中承担枚举名称的稳定性责任。</p>
 */
public final class HealthConstraintPersistenceConverter {

    private HealthConstraintPersistenceConverter() {
    }

    /**
     * 将领域对象转换为持久化对象。
     *
     * <p>所有枚举字段使用 name() 方法转换为字符串，确保数据库存储的稳定性。</p>
     *
     * @param constraint 领域层的健康约束对象
     * @return 持久化层的数据对象
     */
    public static HealthConstraintDataObject toDataObject(HealthConstraint constraint) {
        return new HealthConstraintDataObject(
                constraint.getId(),
                constraint.getConstraintType().name(),
                constraint.getBodyRegion().name(),
                constraint.getSeverity().name(),
                constraint.getTitle(),
                constraint.getDescription(),
                constraint.getSourceType().name(),
                constraint.getSourceNote(),
                constraint.getStatus().name(),
                constraint.getEffectiveFrom(),
                constraint.getEffectiveTo(),
                constraint.getArchiveReason(),
                constraint.getCreatedAt(),
                constraint.getUpdatedAt(),
                constraint.getArchivedAt()
        );
    }

    /**
     * 将持久化对象转换为领域对象。
     *
     * <p>所有枚举字段使用 valueOf() 方法从字符串还原，null 值直接返回 null。</p>
     *
     * @param dataObject 持久化层的数据对象
     * @return 领域层的健康约束对象，若输入为 null 则返回 null
     */
    public static HealthConstraint toDomain(HealthConstraintDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new HealthConstraint(
                dataObject.getId(),
                ConstraintType.valueOf(dataObject.getConstraintType()),
                BodyRegion.valueOf(dataObject.getBodyRegion()),
                ConstraintSeverity.valueOf(dataObject.getSeverity()),
                dataObject.getTitle(),
                dataObject.getDescription(),
                ConstraintSourceType.valueOf(dataObject.getSourceType()),
                dataObject.getSourceNote(),
                ConstraintStatus.valueOf(dataObject.getStatus()),
                dataObject.getEffectiveFrom(),
                dataObject.getEffectiveTo(),
                dataObject.getArchiveReason(),
                dataObject.getCreatedAt(),
                dataObject.getUpdatedAt(),
                dataObject.getArchivedAt()
        );
    }
}
