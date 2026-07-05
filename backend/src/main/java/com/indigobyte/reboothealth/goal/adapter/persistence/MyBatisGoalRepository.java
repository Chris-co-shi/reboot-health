package com.indigobyte.reboothealth.goal.adapter.persistence;

import com.indigobyte.reboothealth.goal.domain.Goal;
import com.indigobyte.reboothealth.goal.domain.GoalFilter;
import com.indigobyte.reboothealth.goal.domain.GoalRepository;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.stereotype.Repository;

@Repository
public class MyBatisGoalRepository implements GoalRepository {

    private final GoalMapper mapper;

    public MyBatisGoalRepository(GoalMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public Optional<Goal> findById(UUID id) {
        return Optional.ofNullable(mapper.findById(id));
    }

    @Override
    public List<Goal> findAll(GoalFilter filter) {
        return mapper.findAll(filter.status(), filter.includeArchived());
    }

    @Override
    public Goal save(Goal goal) {
        if (mapper.findById(goal.getId()) == null) {
            mapper.insert(goal);
        } else {
            mapper.update(goal);
        }
        return goal;
    }
}
