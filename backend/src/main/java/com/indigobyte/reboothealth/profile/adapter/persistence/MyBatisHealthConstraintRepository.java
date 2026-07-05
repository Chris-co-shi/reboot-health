package com.indigobyte.reboothealth.profile.adapter.persistence;

import com.indigobyte.reboothealth.profile.domain.HealthConstraint;
import com.indigobyte.reboothealth.profile.domain.HealthConstraintFilter;
import com.indigobyte.reboothealth.profile.domain.HealthConstraintRepository;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.stereotype.Repository;

@Repository
public class MyBatisHealthConstraintRepository implements HealthConstraintRepository {

    private final HealthConstraintMapper mapper;

    public MyBatisHealthConstraintRepository(HealthConstraintMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public Optional<HealthConstraint> findById(UUID id) {
        return Optional.ofNullable(mapper.findById(id));
    }

    @Override
    public List<HealthConstraint> findAll(HealthConstraintFilter filter) {
        return mapper.findAll(filter.status(), filter.includeArchived());
    }

    @Override
    public HealthConstraint save(HealthConstraint constraint) {
        if (mapper.findById(constraint.getId()) == null) {
            mapper.insert(constraint);
        } else {
            mapper.update(constraint);
        }
        return constraint;
    }
}
