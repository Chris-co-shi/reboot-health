package com.indigobyte.reboothealth.profile.adapter.persistence;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.indigobyte.reboothealth.profile.domain.UserProfile;
import com.indigobyte.reboothealth.profile.domain.UserProfileRepository;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

/**
 * UserProfileRepository 的 MyBatis-Plus 实现。
 *
 * <p>应用服务显式选择 insert 或 update，本类不通过保存前 SELECT 模拟 save。</p>
 */
@Repository
@RequiredArgsConstructor
public class MyBatisUserProfileRepository implements UserProfileRepository {

    private final UserProfileMapper mapper;

    /**
     * 查询当前有效的个人档案。
     *
     * <p>通过 singleton_key = 1 的唯一约束查询，个人版系统只允许一个档案。</p>
     *
     * @return 个人档案的 Optional 包装，若不存在则返回 empty
     */
    @Override
    public Optional<UserProfile> findCurrent() {
        var query = new LambdaQueryWrapper<UserProfileDataObject>()
                .eq(UserProfileDataObject::getSingletonKey, (short) 1);
        return Optional.ofNullable(UserProfilePersistenceConverter.toDomain(mapper.selectOne(query)));
    }

    /**
     * 插入新的个人档案。
     *
     * @param profile 要插入的个人档案领域对象
     */
    @Override
    public void insert(UserProfile profile) {
        mapper.insert(UserProfilePersistenceConverter.toDataObject(profile));
    }

    /**
     * 更新现有的个人档案。
     *
     * @param profile 包含更新数据的个人档案领域对象
     * @return 如果更新成功（影响一行）返回 true，否则返回 false
     */
    @Override
    public boolean update(UserProfile profile) {
        return mapper.updateById(UserProfilePersistenceConverter.toDataObject(profile)) == 1;
    }
}
