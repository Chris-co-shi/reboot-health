package com.indigobyte.reboothealth.profile.domain;

import java.util.Optional;

/**
 * 当前个人档案的领域仓储端口。
 *
 * <p>个人版只允许一个档案，应用服务负责判断创建或更新语义，仓储不通过保存前查询模拟 save。</p>
 */
public interface UserProfileRepository {

    Optional<UserProfile> findCurrent();

    void insert(UserProfile profile);

    boolean update(UserProfile profile);
}
