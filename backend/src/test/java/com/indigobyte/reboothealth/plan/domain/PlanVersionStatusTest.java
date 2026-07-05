package com.indigobyte.reboothealth.plan.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.indigobyte.reboothealth.error.DomainException;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class PlanVersionStatusTest {

    @Test
    void draftCanBeConfirmedAndThenCannotBeEdited() {
        PlanVersion version = draft();

        version.confirm(null, "[]", Instant.parse("2026-07-01T00:00:00Z"));

        assertThat(version.getStatus()).isEqualTo(PlanVersionStatus.CONFIRMED);
        assertThatThrownBy(() -> version.updateDraft("新标题", null, Instant.parse("2026-07-01T00:01:00Z")))
                .isInstanceOf(DomainException.class);
    }

    @Test
    void confirmedCanBeSupersededButCancelledDraftCannotBeChanged() {
        PlanVersion confirmed = draft();
        confirmed.confirm(null, "[]", Instant.parse("2026-07-01T00:00:00Z"));

        confirmed.supersede(Instant.parse("2026-07-01T01:00:00Z"));

        assertThat(confirmed.getStatus()).isEqualTo(PlanVersionStatus.SUPERSEDED);
        assertThatThrownBy(() -> confirmed.supersede(Instant.parse("2026-07-01T02:00:00Z")))
                .isInstanceOf(DomainException.class);

        PlanVersion cancelled = draft();
        cancelled.cancel("人工取消", Instant.parse("2026-07-02T00:00:00Z"));
        assertThatThrownBy(() -> cancelled.confirm(null, "[]", Instant.parse("2026-07-02T01:00:00Z")))
                .isInstanceOf(DomainException.class);
    }

    private PlanVersion draft() {
        return PlanVersion.createDraft(
                UUID.randomUUID(),
                1,
                0,
                LocalDate.of(2026, 7, 6),
                "示例周期",
                null,
                null,
                Instant.parse("2026-07-01T00:00:00Z")
        );
    }
}
