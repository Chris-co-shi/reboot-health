package com.indigobyte.reboothealth.goal.adapter.persistence;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.indigobyte.reboothealth.goal.domain.Goal;
import com.indigobyte.reboothealth.goal.domain.GoalFilter;
import com.indigobyte.reboothealth.goal.domain.GoalRepository;
import com.indigobyte.reboothealth.goal.domain.GoalStatus;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

/**
 * GoalRepository 的 MyBatis-Plus 实现。
 *
 * <p>只负责 DO 与数据库之间的读写；目标状态机和单位组合校验留在领域层。</p>
 */
@Repository
@RequiredArgsConstructor
public class MyBatisGoalRepository implements GoalRepository {

    private final GoalMapper mapper;

    @Override
    public Optional<Goal> findById(UUID id) {
        return Optional.ofNullable(GoalPersistenceConverter.toDomain(mapper.selectById(id)));
    }

    @Override
    public List<Goal> findAll(GoalFilter filter) {
        LambdaQueryWrapper<GoalDataObject> query = new LambdaQueryWrapper<>();
        if (filter.status() != null) {
            query.eq(GoalDataObject::getStatus, filter.status().name());
        }
        if (filter.status() == null && !filter.includeArchived()) {
            query.ne(GoalDataObject::getStatus, GoalStatus.ARCHIVED.name());
        }
        query.orderByAsc(GoalDataObject::getPriority)
                .orderByDesc(GoalDataObject::getCreatedAt);
        return mapper.selectList(query).stream()
                .map(GoalPersistenceConverter::toDomain)
                .toList();
    }

    @Override
    public void insert(Goal goal) {
        mapper.insert(GoalPersistenceConverter.toDataObject(goal));
    }

    @Override
    public boolean update(Goal goal) {
        return mapper.updateById(GoalPersistenceConverter.toDataObject(goal)) == 1;
    }
}
