package com.indigobyte.reboothealth.agent.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.indigobyte.reboothealth.agent.domain.AgentRun;
import com.indigobyte.reboothealth.agent.domain.AgentRunRepository;
import com.indigobyte.reboothealth.agent.domain.AgentRunStatus;
import com.indigobyte.reboothealth.audit.application.AuditLogAppender;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.time.Clock;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * AgentRun 后台执行器。
 *
 * <p>Python 调用不包裹数据库事务；每次状态变化都使用短事务提交，避免 Runtime 等待占用数据库连接和行锁。</p>
 */
@Component
@RequiredArgsConstructor
public class AgentRunWorker {

    private static final String ENTITY_TYPE = "AgentRun";

    private final AgentRunRepository repository;
    private final AgentRuntimeClient runtimeClient;
    private final AgentRunOutputValidator outputValidator;
    private final AuditLogAppender auditLogAppender;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public void execute(UUID runId, String mockMode) {
        AgentRun run = markRunning(runId);
        if (run == null) {
            return;
        }
        try {
            AgentRuntimeResponse response = runtimeClient.execute(new AgentRuntimeRequest(
                    run.getId(),
                    run.getUserId(),
                    run.getDeviceId(),
                    run.getTriggerType().name(),
                    run.getInputSummary(),
                    mockMode
            ));
            markValidating(runId);
            AgentRunOutputValidator.ValidationOutcome validation = outputValidator.validate(response);
            markReady(runId, response, validation);
        } catch (AgentRuntimeException ex) {
            markFailed(runId, ex.code(), sanitize(ex.getMessage()));
        } catch (RuntimeException ex) {
            markFailed(runId, ErrorCode.AGENT_RUNTIME_UNAVAILABLE.name(), "Agent Runtime 调用失败");
        }
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public AgentRun markRunning(UUID runId) {
        AgentRun run = repository.findByIdForUpdate(runId).orElse(null);
        if (run == null || run.getStatus() != AgentRunStatus.CREATED) {
            return null;
        }
        run.markRunning(Instant.now(clock));
        repository.update(run);
        auditLogAppender.append("AGENT_RUN_RUNNING", ENTITY_TYPE, run.getId(), null, redactedRun(run));
        return run;
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void markValidating(UUID runId) {
        AgentRun run = repository.findByIdForUpdate(runId).orElseThrow(() ->
                new ApplicationException(ErrorCode.AGENT_RUN_NOT_FOUND, "AgentRun 不存在", HttpStatus.NOT_FOUND));
        run.markValidating(Instant.now(clock));
        repository.update(run);
        auditLogAppender.append("AGENT_RUN_VALIDATING", ENTITY_TYPE, run.getId(), null, redactedRun(run));
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void markReady(UUID runId, AgentRuntimeResponse response,
                          AgentRunOutputValidator.ValidationOutcome validation) {
        AgentRun run = repository.findByIdForUpdate(runId).orElseThrow(() ->
                new ApplicationException(ErrorCode.AGENT_RUN_NOT_FOUND, "AgentRun 不存在", HttpStatus.NOT_FOUND));
        run.markReady(toJson(response), toJson(validation), Instant.now(clock));
        repository.update(run);
        auditLogAppender.append("AGENT_RUN_READY_FOR_USER_REVIEW", ENTITY_TYPE, run.getId(), null, redactedRun(run));
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void markFailed(UUID runId, String failureCode, String failureMessage) {
        repository.findByIdForUpdate(runId).ifPresent(run -> {
            run.markFailed(failureCode, sanitize(failureMessage), Instant.now(clock));
            repository.update(run);
            auditLogAppender.append("AGENT_RUN_FAILED", ENTITY_TYPE, run.getId(), null, redactedRun(run));
        });
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            throw new ApplicationException(ErrorCode.INTERNAL_ERROR, "AgentRun JSON 序列化失败", HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }

    private Map<String, Object> redactedRun(AgentRun run) {
        return Map.of(
                "runId", run.getId(),
                "userId", run.getUserId(),
                "deviceId", run.getDeviceId(),
                "status", run.getStatus().name(),
                "triggerType", run.getTriggerType().name()
        );
    }

    private String sanitize(String message) {
        if (message == null || message.isBlank()) {
            return "Agent Runtime 调用失败";
        }
        return message.length() > 300 ? message.substring(0, 300) : message;
    }
}
