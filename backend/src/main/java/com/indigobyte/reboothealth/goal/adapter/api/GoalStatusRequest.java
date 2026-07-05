package com.indigobyte.reboothealth.goal.adapter.api;

import com.indigobyte.reboothealth.goal.domain.GoalStatus;
import jakarta.validation.constraints.NotNull;

public record GoalStatusRequest(@NotNull GoalStatus status) {
}
