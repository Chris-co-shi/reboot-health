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

    @Override
    public Optional<UserProfile> findCurrent() {
        var query = new LambdaQueryWrapper<UserProfileDataObject>()
                .eq(UserProfileDataObject::getSingletonKey, (short) 1);
        return Optional.ofNullable(UserProfilePersistenceConverter.toDomain(mapper.selectOne(query)));
    }

    @Override
    public void insert(UserProfile profile) {
        mapper.insert(UserProfilePersistenceConverter.toDataObject(profile));
    }

    @Override
    public boolean update(UserProfile profile) {
        return mapper.updateById(UserProfilePersistenceConverter.toDataObject(profile)) == 1;
    }
}
