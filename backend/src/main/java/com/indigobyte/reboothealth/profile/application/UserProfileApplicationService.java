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

    /**
     * 查询当前个人档案。
     *
     * @return 个人档案的 Optional 包装，若不存在则返回 empty
     */
    @Transactional(readOnly = true)
    public Optional<UserProfile> getCurrentProfile() {
        return userProfileRepository.findCurrent();
    }

    /**
     * 保存或更新当前个人档案。
     *
     * <p>如果档案不存在则创建新档案并记录审计日志；如果存在则进行幂等更新，业务内容无变化时不写审计。</p>
     *
     * @param command 包含档案信息的命令对象
     * @return 保存后的个人档案对象
     * @throws ApplicationException 如果时区不合法或更新冲突
     */
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

    /**
     * 验证时区字符串是否为合法的 IANA 时区标识。
     *
     * @param timezone 时区字符串，如 "Asia/Shanghai"
     * @throws ApplicationException 如果时区不合法
     */
    private void validateTimezone(String timezone) {
        try {
            ZoneId.of(timezone);
        } catch (Exception ex) {
            throw new ApplicationException(ErrorCode.PROFILE_VALIDATION_FAILED, "timezone 必须是合法 IANA 时区", HttpStatus.BAD_REQUEST);
        }
    }

    /**
     * 断言数据库更新是否成功。
     *
     * @param updated 如果为 false 则抛出冲突异常
     * @throws ApplicationException 如果更新失败，表示存在并发冲突
     */
    private void assertUpdated(boolean updated) {
        if (!updated) {
            throw new ApplicationException(ErrorCode.DATA_CONFLICT, "个人档案更新冲突，请刷新后重试", HttpStatus.CONFLICT);
        }
    }

    /**
     * 保存个人档案的命令对象。
     *
     * @param displayName 显示名称
     * @param sex 性别
     * @param birthDate 出生日期
     * @param heightCm 身高（厘米）
     * @param baselineWeightKg 基线体重（千克）
     * @param timezone 时区标识
     */
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
