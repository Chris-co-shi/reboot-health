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
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 个人档案应用服务。
 *
 * <p>本服务负责单档案创建/更新的事务边界：业务变更与审计写入必须同事务提交，幂等更新不写审计。</p>
 */
@Service
@RequiredArgsConstructor
public class UserProfileApplicationService {

    private static final String ENTITY_TYPE = "UserProfile";

    private final UserProfileRepository userProfileRepository;
    private final AuditLogAppender auditLogAppender;
    private final Clock clock;

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
            userProfileRepository.insert(created);
            auditLogAppender.append("PROFILE_CREATED", ENTITY_TYPE, created.getId(), null, created);
            return created;
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
        assertUpdated(userProfileRepository.update(current));
        auditLogAppender.append("PROFILE_UPDATED", ENTITY_TYPE, current.getId(), before, current);
        return current;
    }

    private void validateTimezone(String timezone) {
        try {
            ZoneId.of(timezone);
        } catch (Exception ex) {
            throw new ApplicationException(ErrorCode.PROFILE_VALIDATION_FAILED, "timezone 必须是合法 IANA 时区", HttpStatus.BAD_REQUEST);
        }
    }

    private void assertUpdated(boolean updated) {
        if (!updated) {
            throw new ApplicationException(ErrorCode.DATA_CONFLICT, "个人档案更新冲突，请刷新后重试", HttpStatus.CONFLICT);
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
