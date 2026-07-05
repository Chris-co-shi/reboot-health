package com.indigobyte.reboothealth.plan.adapter.persistence;

import com.indigobyte.reboothealth.plan.domain.Plan;
import com.indigobyte.reboothealth.plan.domain.PlanDay;
import com.indigobyte.reboothealth.plan.domain.PlanItem;
import com.indigobyte.reboothealth.plan.domain.PlanItemType;
import com.indigobyte.reboothealth.plan.domain.PlanVersion;
import com.indigobyte.reboothealth.plan.domain.PlanVersionStatus;

/**
 * Plan 模块领域对象与持久化对象转换器。
 *
 * <p>所有枚举使用 enum.name() / valueOf() 显式转换，避免 MyBatis 隐式枚举处理影响数据库语义。</p>
 */
public final class PlanPersistenceConverter {

    private PlanPersistenceConverter() {
    }

    public static PlanDataObject toDataObject(Plan plan) {
        return new PlanDataObject(plan.getId(), plan.getTitle(), plan.getSummary(), plan.getCreatedAt(), plan.getUpdatedAt());
    }

    public static Plan toPlan(PlanDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new Plan(
                dataObject.getId(),
                dataObject.getTitle(),
                dataObject.getSummary(),
                dataObject.getCreatedAt(),
                dataObject.getUpdatedAt()
        );
    }

    public static PlanVersionDataObject toDataObject(PlanVersion version) {
        return new PlanVersionDataObject(
                version.getId(),
                version.getPlanId(),
                version.getVersionNumber(),
                version.getPeriodRevision(),
                version.getStatus().name(),
                version.getStartDate(),
                version.getEndDate(),
                version.getTitle(),
                version.getSummary(),
                version.getCopiedFromVersionId(),
                version.getSupersedesVersionId(),
                version.getHealthConstraintSnapshot(),
                version.getRevision(),
                version.getConfirmedAt(),
                version.getSupersededAt(),
                version.getCancelledAt(),
                version.getCancelReason(),
                version.getCreatedAt(),
                version.getUpdatedAt()
        );
    }

    public static PlanVersion toVersion(PlanVersionDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new PlanVersion(
                dataObject.getId(),
                dataObject.getPlanId(),
                dataObject.getVersionNumber(),
                dataObject.getPeriodRevision(),
                PlanVersionStatus.valueOf(dataObject.getStatus()),
                dataObject.getStartDate(),
                dataObject.getEndDate(),
                dataObject.getTitle(),
                dataObject.getSummary(),
                dataObject.getCopiedFromVersionId(),
                dataObject.getSupersedesVersionId(),
                dataObject.getHealthConstraintSnapshot(),
                dataObject.getRevision(),
                dataObject.getConfirmedAt(),
                dataObject.getSupersededAt(),
                dataObject.getCancelledAt(),
                dataObject.getCancelReason(),
                dataObject.getCreatedAt(),
                dataObject.getUpdatedAt()
        );
    }

    public static PlanDayDataObject toDataObject(PlanDay day) {
        return new PlanDayDataObject(
                day.getId(),
                day.getVersionId(),
                day.getDayDate(),
                day.getTitle(),
                day.getNote(),
                day.getSortOrder(),
                day.getCreatedAt(),
                day.getUpdatedAt()
        );
    }

    public static PlanDay toDay(PlanDayDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new PlanDay(
                dataObject.getId(),
                dataObject.getVersionId(),
                dataObject.getDayDate(),
                dataObject.getTitle(),
                dataObject.getNote(),
                dataObject.getSortOrder(),
                dataObject.getCreatedAt(),
                dataObject.getUpdatedAt()
        );
    }

    public static PlanItemDataObject toDataObject(PlanItem item) {
        return new PlanItemDataObject(
                item.getId(),
                item.getDayId(),
                item.getGoalId(),
                item.getItemType().name(),
                item.getTitle(),
                item.getDescription(),
                item.getPlannedSets(),
                item.getPlannedReps(),
                item.getPlannedDurationMinutes(),
                item.getPlannedDistanceMeters(),
                item.getPlannedRpe(),
                item.getSortOrder(),
                item.getCreatedAt(),
                item.getUpdatedAt()
        );
    }

    public static PlanItem toItem(PlanItemDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new PlanItem(
                dataObject.getId(),
                dataObject.getDayId(),
                dataObject.getGoalId(),
                PlanItemType.valueOf(dataObject.getItemType()),
                dataObject.getTitle(),
                dataObject.getDescription(),
                dataObject.getPlannedSets(),
                dataObject.getPlannedReps(),
                dataObject.getPlannedDurationMinutes(),
                dataObject.getPlannedDistanceMeters(),
                dataObject.getPlannedRpe(),
                dataObject.getSortOrder(),
                dataObject.getCreatedAt(),
                dataObject.getUpdatedAt()
        );
    }
}
