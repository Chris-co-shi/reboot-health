package com.indigobyte.reboothealth.profile.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 健康约束聚合的仓储端口。
 *
 * <p>端口只表达持久化动作和查询条件，状态流转、归档和规则校验由领域对象与应用服务负责。</p>
 */
public interface HealthConstraintRepository {

    Optional<HealthConstraint> findById(UUID id);

    List<HealthConstraint> findAll(HealthConstraintFilter filter);

    void insert(HealthConstraint constraint);

    boolean update(HealthConstraint constraint);
}
