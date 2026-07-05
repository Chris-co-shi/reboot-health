package com.indigobyte.reboothealth.profile.adapter.persistence;

import com.indigobyte.reboothealth.profile.domain.UserProfile;
import java.util.UUID;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface UserProfileMapper {

    @Select("SELECT * FROM app_user_profile WHERE singleton_key = 1")
    UserProfile findCurrent();

    @Select("SELECT * FROM app_user_profile WHERE id = #{id}")
    UserProfile findById(UUID id);

    @Insert("""
            INSERT INTO app_user_profile (
                id, singleton_key, display_name, sex, birth_date, height_cm,
                baseline_weight_kg, timezone, created_at, updated_at
            ) VALUES (
                #{id}, 1, #{displayName}, #{sex}, #{birthDate}, #{heightCm},
                #{baselineWeightKg}, #{timezone}, #{createdAt}, #{updatedAt}
            )
            """)
    void insert(UserProfile profile);

    @Update("""
            UPDATE app_user_profile
            SET display_name = #{displayName},
                sex = #{sex},
                birth_date = #{birthDate},
                height_cm = #{heightCm},
                baseline_weight_kg = #{baselineWeightKg},
                timezone = #{timezone},
                updated_at = #{updatedAt}
            WHERE id = #{id}
            """)
    void update(UserProfile profile);
}
