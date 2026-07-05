package com.indigobyte.reboothealth.profile.domain;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.time.Instant;
import java.time.LocalDate;
import org.junit.jupiter.api.Test;

class HealthConstraintTest {

    @Test
    void effectiveToCannotBeBeforeEffectiveFrom() {
        assertThatThrownBy(() -> HealthConstraint.create(
                ConstraintType.CERVICAL_LIMITATION,
                BodyRegion.CERVICAL_SPINE,
                ConstraintSeverity.MEDIUM,
                "示例活动限制",
                "示例描述：避免不适动作",
                ConstraintSourceType.USER_REPORTED,
                null,
                LocalDate.parse("2026-07-10"),
                LocalDate.parse("2026-07-01"),
                Instant.parse("2026-07-01T00:00:00Z")
        ))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.HEALTH_CONSTRAINT_INVALID_DATE_RANGE);
    }

    @Test
    void archiveReasonIsRequired() {
        HealthConstraint constraint = HealthConstraint.create(
                ConstraintType.TRAINING_PRECAUTION,
                BodyRegion.FULL_BODY,
                ConstraintSeverity.MEDIUM,
                "示例训练注意",
                "示例描述：根据主观状态调整",
                ConstraintSourceType.USER_REPORTED,
                null,
                null,
                null,
                Instant.parse("2026-07-01T00:00:00Z")
        );

        assertThatThrownBy(() -> constraint.archive(" ", Instant.parse("2026-07-02T00:00:00Z")))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.VALIDATION_ERROR);
    }
}
