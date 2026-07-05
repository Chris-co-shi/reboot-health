package com.indigobyte.reboothealth.goal.adapter.api;

import com.indigobyte.reboothealth.goal.domain.GoalType;
import com.indigobyte.reboothealth.goal.domain.GoalUnit;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.LocalDate;

public record GoalRequest(
        @NotNull GoalType goalType,
        @NotBlank @Size(max = 100) String title,
        @DecimalMin("0.000") BigDecimal targetValue,
        @NotNull GoalUnit unit,
        @DecimalMin("0.000") BigDecimal baselineValue,
        LocalDate targetDate,
        @NotNull @Min(1) @Max(5) Integer priority
) {
}
