package com.indigobyte.reboothealth.profile.application;

import com.indigobyte.reboothealth.audit.application.AuditLogAppender;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import com.indigobyte.reboothealth.profile.domain.Sex;
import com.indigobyte.reboothealth.profile.domain.UserProfile;
import com.indigobyte.reboothealth.profile.domain.UserProfileRepository;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.Optional;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UserProfileApplicationService {

    private static final String ENTITY_TYPE = "UserProfile";

    private final UserProfileRepository userProfileRepository;
    private final AuditLogAppender auditLogAppender;
    private final Clock clock;

    public UserProfileApplicationService(UserProfileRepository userProfileRepository,
                                         AuditLogAppender auditLogAppender,
                                         Clock clock) {
        this.userProfileRepository = userProfileRepository;
        this.auditLogAppender = auditLogAppender;
        this.clock = clock;
    }

    @Transactional(readOnly = true)
    public Optional<UserProfile> getCurrentProfile() {
        return userProfileRepository.findCurrent();
    }

    @Transactional
    public UserProfile saveCurrentProfile(SaveUserProfileCommand command) {
        validateTimezone(command.timezone());
        Instant now = Instant.now(clock);
        Optional<UserProfile> existing = userProfileRepository.findCurrent();

        if (existing.isEmpty()) {
            UserProfile created = UserProfile.create(
                    command.displayName(),
                    command.sex(),
                    command.birthDate(),
                    command.heightCm(),
                    command.baselineWeightKg(),
                    command.timezone(),
                    now
            );
            UserProfile saved = userProfileRepository.save(created);
            auditLogAppender.append("PROFILE_CREATED", ENTITY_TYPE, saved.getId(), null, saved);
            return saved;
        }

        UserProfile current = existing.get();
        UserProfile requested = new UserProfile(
                current.getId(),
                command.displayName(),
                command.sex(),
                command.birthDate(),
                command.heightCm(),
                command.baselineWeightKg(),
                command.timezone(),
                current.getCreatedAt(),
                current.getUpdatedAt()
        );
        if (current.hasSameBusinessContent(requested)) {
            return current;
        }

        UserProfile before = new UserProfile(
                current.getId(),
                current.getDisplayName(),
                current.getSex(),
                current.getBirthDate(),
                current.getHeightCm(),
                current.getBaselineWeightKg(),
                current.getTimezone(),
                current.getCreatedAt(),
                current.getUpdatedAt()
        );
        current.updateFrom(requested, now);
        UserProfile saved = userProfileRepository.save(current);
        auditLogAppender.append("PROFILE_UPDATED", ENTITY_TYPE, saved.getId(), before, saved);
        return saved;
    }

    private void validateTimezone(String timezone) {
        try {
            ZoneId.of(timezone);
        } catch (Exception ex) {
            throw new ApplicationException(ErrorCode.PROFILE_VALIDATION_FAILED, "timezone 必须是合法 IANA 时区", HttpStatus.BAD_REQUEST);
        }
    }

    public record SaveUserProfileCommand(
            String displayName,
            Sex sex,
            LocalDate birthDate,
            BigDecimal heightCm,
            BigDecimal baselineWeightKg,
            String timezone
    ) {
    }
}
