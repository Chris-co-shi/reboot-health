package com.indigobyte.reboothealth.goal.domain;

public record GoalFilter(GoalStatus status, boolean includeArchived) {
}
