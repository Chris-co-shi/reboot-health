package com.indigobyte.reboothealth.profile.domain;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.assertThatCode;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import org.junit.jupiter.api.Test;

class ConstraintStatusTest {

    @Test
    void activeCanMoveToInactiveResolvedOrArchived() {
        assertThatCode(() -> ConstraintStatus.ACTIVE.assertCanTransitionTo(ConstraintStatus.INACTIVE))
                .doesNotThrowAnyException();
        assertThatCode(() -> ConstraintStatus.ACTIVE.assertCanTransitionTo(ConstraintStatus.RESOLVED))
                .doesNotThrowAnyException();
        assertThatCode(() -> ConstraintStatus.ACTIVE.assertCanTransitionTo(ConstraintStatus.ARCHIVED))
                .doesNotThrowAnyException();
    }

    @Test
    void resolvedCannotMoveBackToActive() {
        assertThatThrownBy(() -> ConstraintStatus.RESOLVED.assertCanTransitionTo(ConstraintStatus.ACTIVE))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.HEALTH_CONSTRAINT_INVALID_STATUS_TRANSITION);
    }

    @Test
    void archivedCannotMoveToAnyStatus() {
        assertThatThrownBy(() -> ConstraintStatus.ARCHIVED.assertCanTransitionTo(ConstraintStatus.ACTIVE))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.HEALTH_CONSTRAINT_INVALID_STATUS_TRANSITION);
    }

    @Test
    void sameStatusIsNotAValidTransition() {
        assertThatThrownBy(() -> ConstraintStatus.ACTIVE.assertCanTransitionTo(ConstraintStatus.ACTIVE))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.HEALTH_CONSTRAINT_INVALID_STATUS_TRANSITION);
    }
}
