package com.indigobyte.reboothealth.profile.domain;

import java.util.Optional;

public interface UserProfileRepository {

    Optional<UserProfile> findCurrent();

    UserProfile save(UserProfile profile);
}
