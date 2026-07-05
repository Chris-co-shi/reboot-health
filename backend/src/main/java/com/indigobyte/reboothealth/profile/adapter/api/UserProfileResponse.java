package com.indigobyte.reboothealth.profile.adapter.api;

import com.indigobyte.reboothealth.profile.domain.Sex;
import com.indigobyte.reboothealth.profile.domain.UserProfile;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

public record UserProfileResponse(
        UUID id,
        String displayName,
        Sex sex,
        LocalDate birthDate,
        BigDecimal heightCm,
        BigDecimal baselineWeightKg,
        String timezone,
        Instant createdAt,
        Instant updatedAt
) {
    public static UserProfileResponse from(UserProfile profile) {
        return new UserProfileResponse(
                profile.getId(),
                profile.getDisplayName(),
                profile.getSex(),
                profile.getBirthDate(),
                profile.getHeightCm(),
                profile.getBaselineWeightKg(),
                profile.getTimezone(),
                profile.getCreatedAt(),
                profile.getUpdatedAt()
        );
    }
}
