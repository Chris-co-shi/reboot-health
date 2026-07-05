package com.indigobyte.reboothealth.profile.adapter.persistence;

import com.indigobyte.reboothealth.profile.domain.UserProfile;
import com.indigobyte.reboothealth.profile.domain.UserProfileRepository;
import java.util.Optional;
import org.springframework.stereotype.Repository;

@Repository
public class MyBatisUserProfileRepository implements UserProfileRepository {

    private final UserProfileMapper mapper;

    public MyBatisUserProfileRepository(UserProfileMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public Optional<UserProfile> findCurrent() {
        return Optional.ofNullable(mapper.findCurrent());
    }

    @Override
    public UserProfile save(UserProfile profile) {
        if (mapper.findById(profile.getId()) == null) {
            mapper.insert(profile);
        } else {
            mapper.update(profile);
        }
        return profile;
    }
}
