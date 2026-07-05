package com.indigobyte.reboothealth.goal.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface GoalRepository {

    Optional<Goal> findById(UUID id);

    List<Goal> findAll(GoalFilter filter);

    Goal save(Goal goal);
}
