package com.indigobyte.reboothealth.plan.application;

import com.indigobyte.reboothealth.profile.domain.UserProfile;
import com.indigobyte.reboothealth.profile.domain.UserProfileRepository;
import java.time.Clock;
import java.time.DateTimeException;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * 当前计划日期解析器。
 *
 * <p>当前计划必须按个人档案时区计算；档案不存在或时区数据异常时使用显式配置的默认时区，避免落回 JVM 默认时区。</p>
 */
@Component
public class CurrentPlanDateProvider {

    private final UserProfileRepository userProfileRepository;
    private final Clock clock;
    private final ZoneId defaultZoneId;

    public CurrentPlanDateProvider(
            UserProfileRepository userProfileRepository,
            Clock clock,
            @Value("${app.default-timezone}") String defaultTimezone
    ) {
        this.userProfileRepository = userProfileRepository;
        this.clock = clock;
        this.defaultZoneId = ZoneId.of(defaultTimezone);
    }

    /**
     * 返回当前用户语义下的本地日期。
     */
    public LocalDate currentDate() {
        ZoneId zoneId = userProfileRepository.findCurrent()
                .map(UserProfile::getTimezone)
                .map(this::parseZoneOrDefault)
                .orElse(defaultZoneId);
        return Instant.now(clock).atZone(zoneId).toLocalDate();
    }

    private ZoneId parseZoneOrDefault(String timezone) {
        try {
            return ZoneId.of(timezone);
        } catch (DateTimeException ex) {
            return defaultZoneId;
        }
    }
}
