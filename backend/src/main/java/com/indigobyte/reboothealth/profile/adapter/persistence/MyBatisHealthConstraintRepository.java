package com.indigobyte.reboothealth.profile.adapter.persistence;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.indigobyte.reboothealth.profile.domain.ConstraintStatus;
import com.indigobyte.reboothealth.profile.domain.HealthConstraint;
import com.indigobyte.reboothealth.profile.domain.HealthConstraintFilter;
import com.indigobyte.reboothealth.profile.domain.HealthConstraintRepository;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

/**
 * HealthConstraintRepository 的 MyBatis-Plus 实现。
 *
 * <p>查询条件在适配器中转换为数据库字符串，领域枚举不直接进入持久化对象。</p>
 */
@Repository
@RequiredArgsConstructor
public class MyBatisHealthConstraintRepository implements HealthConstraintRepository {

    private final HealthConstraintMapper mapper;

    @Override
    public Optional<HealthConstraint> findById(UUID id) {
        return Optional.ofNullable(HealthConstraintPersistenceConverter.toDomain(mapper.selectById(id)));
    }

    @Override
    public List<HealthConstraint> findAll(HealthConstraintFilter filter) {
        LambdaQueryWrapper<HealthConstraintDataObject> query = new LambdaQueryWrapper<>();
        if (filter.status() != null) {
            query.eq(HealthConstraintDataObject::getStatus, filter.status().name());
        }
        if (filter.status() == null && !filter.includeArchived()) {
            query.ne(HealthConstraintDataObject::getStatus, ConstraintStatus.ARCHIVED.name());
        }
        query.orderByDesc(HealthConstraintDataObject::getCreatedAt);
        return mapper.selectList(query).stream()
                .map(HealthConstraintPersistenceConverter::toDomain)
                .toList();
    }

    @Override
    public void insert(HealthConstraint constraint) {
        mapper.insert(HealthConstraintPersistenceConverter.toDataObject(constraint));
    }

    @Override
    public boolean update(HealthConstraint constraint) {
        return mapper.updateById(HealthConstraintPersistenceConverter.toDataObject(constraint)) == 1;
    }
}
