package com.indigobyte.reboothealth.agent.application;

import com.indigobyte.reboothealth.agent.domain.AgentRunRepository;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/**
 * AgentRun 启动恢复服务。
 *
 * <p>服务重启后不重新调用 Python；只把超过阈值仍处于非终态的运行标记为 EXPIRED。</p>
 */
@Component
@RequiredArgsConstructor
public class AgentRunRecoveryService implements ApplicationRunner {

    private final AgentRunRepository repository;
    private final Clock clock;

    @Value("${app.agent-runtime.stale-timeout-seconds:300}")
    private long staleTimeoutSeconds;

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        Instant now = Instant.now(clock);
        if (now == null) {
            return;
        }
        repository.expireStaleRuns(now.minus(Duration.ofSeconds(staleTimeoutSeconds)), now);
    }
}
