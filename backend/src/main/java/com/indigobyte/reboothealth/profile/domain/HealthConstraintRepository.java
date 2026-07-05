package com.indigobyte.reboothealth.profile.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface HealthConstraintRepository {

    Optional<HealthConstraint> findById(UUID id);

    List<HealthConstraint> findAll(HealthConstraintFilter filter);

    HealthConstraint save(HealthConstraint constraint);
}
