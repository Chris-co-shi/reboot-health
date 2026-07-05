package com.indigobyte.reboothealth.profile.adapter.api;

import com.indigobyte.reboothealth.profile.domain.BodyRegion;
import com.indigobyte.reboothealth.profile.domain.ConstraintSeverity;
import com.indigobyte.reboothealth.profile.domain.ConstraintSourceType;
import com.indigobyte.reboothealth.profile.domain.ConstraintType;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;

public record HealthConstraintRequest(
        @NotNull ConstraintType constraintType,
        @NotNull BodyRegion bodyRegion,
        @NotNull ConstraintSeverity severity,
        @NotBlank @Size(max = 100) String title,
        @Size(max = 2000) String description,
        @NotNull ConstraintSourceType sourceType,
        @Size(max = 1000) String sourceNote,
        LocalDate effectiveFrom,
        LocalDate effectiveTo
) {
    @AssertTrue(message = "effectiveTo 不能早于 effectiveFrom")
    public boolean isDateRangeValid() {
        return effectiveFrom == null || effectiveTo == null || !effectiveTo.isBefore(effectiveFrom);
    }
}
