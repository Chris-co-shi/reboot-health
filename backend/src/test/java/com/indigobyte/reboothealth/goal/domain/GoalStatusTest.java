package com.indigobyte.reboothealth.goal.domain;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.indigobyte.reboothealth.error.DomainException;
import com.indigobyte.reboothealth.error.ErrorCode;
import org.junit.jupiter.api.Test;

class GoalStatusTest {

    @Test
    void activeAndPausedCanUseAllowedTransitions() {
        assertThatCode(() -> GoalStatus.ACTIVE.assertCanTransitionTo(GoalStatus.PAUSED))
                .doesNotThrowAnyException();
        assertThatCode(() -> GoalStatus.ACTIVE.assertCanTransitionTo(GoalStatus.COMPLETED))
                .doesNotThrowAnyException();
        assertThatCode(() -> GoalStatus.PAUSED.assertCanTransitionTo(GoalStatus.ACTIVE))
                .doesNotThrowAnyException();
        assertThatCode(() -> GoalStatus.PAUSED.assertCanTransitionTo(GoalStatus.CANCELLED))
                .doesNotThrowAnyException();
    }

    @Test
    void completedAndCancelledCannotMoveBackToActiveByNormalStatusChange() {
        assertThatThrownBy(() -> GoalStatus.COMPLETED.assertCanTransitionTo(GoalStatus.ACTIVE))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.GOAL_INVALID_STATUS_TRANSITION);
    }

    @Test
    void activePausedCompletedAndCancelledCanArchiveThroughDedicatedFlow() {
        assertThatCode(GoalStatus.ACTIVE::assertCanArchive).doesNotThrowAnyException();
        assertThatCode(GoalStatus.PAUSED::assertCanArchive).doesNotThrowAnyException();
        assertThatCode(GoalStatus.COMPLETED::assertCanArchive).doesNotThrowAnyException();
        assertThatCode(GoalStatus.CANCELLED::assertCanArchive).doesNotThrowAnyException();
    }

    @Test
    void normalStatusChangeCannotArchive() {
        assertThatThrownBy(() -> GoalStatus.ACTIVE.assertCanTransitionTo(GoalStatus.ARCHIVED))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.GOAL_INVALID_STATUS_TRANSITION);
    }

    @Test
    void archivedCannotMoveToAnyStatus() {
        assertThatThrownBy(() -> GoalStatus.ARCHIVED.assertCanTransitionTo(GoalStatus.ACTIVE))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.GOAL_INVALID_STATUS_TRANSITION);
    }

    @Test
    void sameStatusIsNotAValidTransition() {
        assertThatThrownBy(() -> GoalStatus.ACTIVE.assertCanTransitionTo(GoalStatus.ACTIVE))
                .isInstanceOf(DomainException.class)
                .extracting("code")
                .isEqualTo(ErrorCode.GOAL_INVALID_STATUS_TRANSITION);
    }
}
