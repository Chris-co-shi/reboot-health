package com.indigobyte.reboothealth.profile.domain;

import java.util.Optional;

/**
 * 当前个人档案的领域仓储端口。
 *
 * <p>个人版只允许一个档案，应用服务负责判断创建或更新语义，仓储不通过保存前查询模拟 save。</p>
 */
public interface UserProfileRepository {

    /**
     * 查询当前有效的个人健康档案。
     *
     * <p>个人版系统只允许存在一个档案，返回 Optional 以处理尚未创建档案的情况。</p>
     *
     * @return 当前档案的 Optional 包装，若不存在则返回 empty
     */
    Optional<UserProfile> findCurrent();

    /**
     * 插入新的个人健康档案。
     *
     * <p>仅在系统中尚不存在档案时调用。若已存在档案应使用 update 方法。</p>
     *
     * @param profile 要插入的个人档案对象
     * @throws IllegalStateException 如果系统中已存在档案
     */
    void insert(UserProfile profile);

    /**
     * 更新现有的个人健康档案。
     *
     * <p>用于修改档案的业务字段，如姓名、身高、基线体重等。</p>
     *
     * @param profile 包含更新数据的个人档案对象
     * @return 如果更新成功返回 true，如果档案不存在返回 false
     */
    boolean update(UserProfile profile);
}
