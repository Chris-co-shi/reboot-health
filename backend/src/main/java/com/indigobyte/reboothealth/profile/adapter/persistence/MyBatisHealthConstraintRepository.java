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

    /**
     * 根据 ID 查询健康约束。
     *
     * @param id 约束的唯一标识符
     * @return 约束对象的 Optional 包装，若不存在则返回 empty
     */
    @Override
    public Optional<HealthConstraint> findById(UUID id) {
        return Optional.ofNullable(HealthConstraintPersistenceConverter.toDomain(mapper.selectById(id)));
    }

    /**
     * 根据过滤条件查询健康约束列表。
     *
     * <p>如果指定了状态则按状态过滤；如果未指定状态且 includeArchived=false，则排除 ARCHIVED 状态的约束。</p>
     *
     * @param filter 过滤条件
     * @return 符合条件的约束列表，按创建时间倒序排列
     */
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

    /**
     * 插入新的健康约束。
     *
     * @param constraint 要插入的约束领域对象
     */
    @Override
    public void insert(HealthConstraint constraint) {
        mapper.insert(HealthConstraintPersistenceConverter.toDataObject(constraint));
    }

    /**
     * 更新现有的健康约束。
     *
     * @param constraint 包含更新数据的约束领域对象
     * @return 如果更新成功（影响一行）返回 true，否则返回 false
     */
    @Override
    public boolean update(HealthConstraint constraint) {
        return mapper.updateById(HealthConstraintPersistenceConverter.toDataObject(constraint)) == 1;
    }
}
