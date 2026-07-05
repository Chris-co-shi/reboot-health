package com.indigobyte.reboothealth.goal.adapter.persistence;

import com.indigobyte.reboothealth.goal.domain.Goal;
import com.indigobyte.reboothealth.goal.domain.GoalStatus;
import com.indigobyte.reboothealth.goal.domain.GoalType;
import com.indigobyte.reboothealth.goal.domain.GoalUnit;

/**
 * Goal 聚合与 goal 持久化对象之间的转换器。
 *
 * <p>转换器负责所有枚举名称的显式读写，防止 MyBatis-Plus 隐式枚举行为影响数据库内容。</p>
 */
public final class GoalPersistenceConverter {

    private GoalPersistenceConverter() {
    }

    public static GoalDataObject toDataObject(Goal goal) {
        return new GoalDataObject(
                goal.getId(),
                goal.getGoalType().name(),
                goal.getTitle(),
                goal.getTargetValue(),
                goal.getUnit().name(),
                goal.getBaselineValue(),
                goal.getTargetDate(),
                goal.getStatus().name(),
                goal.getPriority(),
                goal.getArchiveReason(),
                goal.getCreatedAt(),
                goal.getUpdatedAt(),
                goal.getArchivedAt()
        );
    }

    public static Goal toDomain(GoalDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new Goal(
                dataObject.getId(),
                GoalType.valueOf(dataObject.getGoalType()),
                dataObject.getTitle(),
                dataObject.getTargetValue(),
                GoalUnit.valueOf(dataObject.getUnit()),
                dataObject.getBaselineValue(),
                dataObject.getTargetDate(),
                GoalStatus.valueOf(dataObject.getStatus()),
                dataObject.getPriority(),
                dataObject.getArchiveReason(),
                dataObject.getCreatedAt(),
                dataObject.getUpdatedAt(),
                dataObject.getArchivedAt()
        );
    }
}
