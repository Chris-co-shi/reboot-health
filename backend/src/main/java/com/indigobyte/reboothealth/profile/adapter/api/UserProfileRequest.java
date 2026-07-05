package com.indigobyte.reboothealth.profile.adapter.api;

import com.indigobyte.reboothealth.profile.domain.Sex;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PastOrPresent;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.LocalDate;

public record UserProfileRequest(
        @NotBlank @Size(max = 60) String displayName,
        @NotNull Sex sex,
        @PastOrPresent LocalDate birthDate,
        @DecimalMin("100.00") @DecimalMax("250.00") BigDecimal heightCm,
        @DecimalMin("30.00") @DecimalMax("300.00") BigDecimal baselineWeightKg,
        @NotBlank @Size(max = 64) String timezone
) {
}
