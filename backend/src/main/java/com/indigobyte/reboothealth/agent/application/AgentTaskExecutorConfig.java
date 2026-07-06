package com.indigobyte.reboothealth.agent.application;

import java.util.concurrent.Executor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

/**
 * AgentRun 异步执行线程池配置。
 *
 * <p>避免直接创建裸线程，并让关闭时可以等待已提交任务完成。</p>
 */
@Configuration
public class AgentTaskExecutorConfig {

    @Bean
    public Executor agentTaskExecutor(
            @Value("${app.agent-runtime.executor.core-size:1}") int coreSize,
            @Value("${app.agent-runtime.executor.max-size:2}") int maxSize,
            @Value("${app.agent-runtime.executor.queue-capacity:16}") int queueCapacity
    ) {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(coreSize);
        executor.setMaxPoolSize(maxSize);
        executor.setQueueCapacity(queueCapacity);
        executor.setThreadNamePrefix("agent-run-");
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(10);
        executor.initialize();
        return executor;
    }
}
