package com.indigobyte.reboothealth.goal.adapter.api;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record GoalArchiveRequest(@NotBlank @Size(max = 300) String archiveReason) {
}
