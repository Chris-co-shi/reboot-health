package com.indigobyte.reboothealth.goal.domain;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.math.BigDecimal;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class GoalTargetValidationTest {

    @Test
    void weightGoalMustUseKg() {
        assertThatThrownBy(() -> Goal.create(
                GoalType.WEIGHT,
                "减重目标",
                new BigDecimal("80.0"),
                GoalUnit.CM,
                new BigDecimal("94.0"),
                null,
                1,
                Instant.parse("2026-01-01T00:00:00Z")
        ))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.GOAL_INVALID_TARGET);
    }

    @Test
    void noneUnitCannotCarryNumericValues() {
        assertThatThrownBy(() -> Goal.create(
                GoalType.OTHER,
                "保持状态",
                BigDecimal.ONE,
                GoalUnit.NONE,
                null,
                null,
                3,
                Instant.parse("2026-01-01T00:00:00Z")
        ))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.GOAL_INVALID_TARGET);
    }

    @Test
    void negativeTargetValueIsRejected() {
        assertThatThrownBy(() -> Goal.create(
                GoalType.SWIMMING,
                "游泳距离",
                new BigDecimal("-1"),
                GoalUnit.METERS,
                null,
                null,
                2,
                Instant.parse("2026-01-01T00:00:00Z")
        ))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.GOAL_INVALID_TARGET);
    }
}
