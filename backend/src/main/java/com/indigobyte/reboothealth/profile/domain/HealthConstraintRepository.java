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

    /**
     * 根据 ID 查询健康约束。
     *
     * @param id 约束的唯一标识符
     * @return 约束对象的 Optional 包装，若不存在则返回 empty
     */
    Optional<HealthConstraint> findById(UUID id);

    /**
     * 根据过滤条件查询健康约束列表。
     *
     * @param filter 过滤条件，包含状态和是否包含已归档约束
     * @return 符合条件的约束列表，按创建时间倒序排列
     */
    List<HealthConstraint> findAll(HealthConstraintFilter filter);

    /**
     * 插入新的健康约束。
     *
     * <p>新创建的约束默认为 ACTIVE 状态。</p>
     *
     * @param constraint 要插入的约束对象
     */
    void insert(HealthConstraint constraint);

    /**
     * 更新现有的健康约束。
     *
     * <p>用于保存约束的业务字段修改、状态变更或归档操作。</p>
     *
     * @param constraint 包含更新数据的约束对象
     * @return 如果更新成功返回 true，如果约束不存在返回 false
     */
    boolean update(HealthConstraint constraint);
}
