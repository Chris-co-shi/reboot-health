package com.indigobyte.reboothealth.plan.adapter.persistence;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;

/**
 * plan_version_goal 的目标摘要快照读取对象。
 */
@Getter
@Setter
public class PlanVersionGoalSnapshotDataObject {

    private UUID goalId;
    private String goalTitle;
    private String goalType;
    private String goalStatus;
    private BigDecimal targetValue;
    private String unit;
    private BigDecimal baselineValue;
    private LocalDate targetDate;
}
