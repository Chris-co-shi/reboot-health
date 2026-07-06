package com.indigobyte.reboothealth.agent.application;

import java.util.concurrent.Executor;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/**
 * AgentRun 创建事务提交后的异步派发器。
 */
@Component
@RequiredArgsConstructor
public class AgentRunAsyncDispatcher {

    @Qualifier("agentTaskExecutor")
    private final Executor executor;
    private final AgentRunWorker worker;

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void onAgentRunCreated(AgentRunCreatedEvent event) {
        executor.execute(() -> worker.execute(event.runId(), event.mockMode()));
    }
}
