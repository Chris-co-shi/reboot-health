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
