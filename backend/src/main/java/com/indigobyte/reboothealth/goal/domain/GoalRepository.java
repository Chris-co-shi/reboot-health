package com.indigobyte.reboothealth.goal.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 目标聚合的仓储端口。
 *
 * <p>创建和更新由应用服务显式选择，仓储不提供泛化 save，以避免 UUID 已生成时的 insert/update 歧义。</p>
 */
public interface GoalRepository {

    Optional<Goal> findById(UUID id);

    List<Goal> findAll(GoalFilter filter);

    void insert(Goal goal);

    boolean update(Goal goal);
}
