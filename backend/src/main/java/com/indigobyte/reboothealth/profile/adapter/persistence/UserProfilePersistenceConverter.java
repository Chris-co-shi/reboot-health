package com.indigobyte.reboothealth.profile.adapter.persistence;

import com.indigobyte.reboothealth.profile.domain.Sex;
import com.indigobyte.reboothealth.profile.domain.UserProfile;

/**
 * UserProfile 聚合与 app_user_profile 持久化对象之间的转换器。
 *
 * <p>枚举字段使用 enum.name() 和 Enum.valueOf() 显式转换，避免持久化层隐式枚举映射。</p>
 */
public final class UserProfilePersistenceConverter {

    private static final short SINGLETON_KEY = 1;

    private UserProfilePersistenceConverter() {
    }

    /**
     * 将领域对象转换为持久化对象。
     *
     * <p>枚举字段使用 name() 方法转换为字符串，singletonKey 固定为 1。</p>
     *
     * @param profile 领域层的个人档案对象
     * @return 持久化层的数据对象
     */
    public static UserProfileDataObject toDataObject(UserProfile profile) {
        return new UserProfileDataObject(
                profile.getId(),
                SINGLETON_KEY,
                profile.getDisplayName(),
                profile.getSex().name(),
                profile.getBirthDate(),
                profile.getHeightCm(),
                profile.getBaselineWeightKg(),
                profile.getTimezone(),
                profile.getCreatedAt(),
                profile.getUpdatedAt()
        );
    }

    /**
     * 将持久化对象转换为领域对象。
     *
     * <p>枚举字段使用 valueOf() 方法从字符串还原，null 值直接返回 null。</p>
     *
     * @param dataObject 持久化层的数据对象
     * @return 领域层的个人档案对象，若输入为 null 则返回 null
     */
    public static UserProfile toDomain(UserProfileDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new UserProfile(
                dataObject.getId(),
                dataObject.getDisplayName(),
                Sex.valueOf(dataObject.getSex()),
                dataObject.getBirthDate(),
                dataObject.getHeightCm(),
                dataObject.getBaselineWeightKg(),
                dataObject.getTimezone(),
                dataObject.getCreatedAt(),
                dataObject.getUpdatedAt()
        );
    }
}
