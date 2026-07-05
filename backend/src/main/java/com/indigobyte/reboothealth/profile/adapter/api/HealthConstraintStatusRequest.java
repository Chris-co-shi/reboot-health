package com.indigobyte.reboothealth.profile.adapter.api;

import com.indigobyte.reboothealth.profile.domain.ConstraintStatus;
import jakarta.validation.constraints.NotNull;

public record HealthConstraintStatusRequest(@NotNull ConstraintStatus status) {
}
