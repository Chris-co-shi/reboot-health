package com.indigobyte.reboothealth.agent.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.indigobyte.reboothealth.agent.domain.AgentRun;
import com.indigobyte.reboothealth.agent.domain.AgentRunRepository;
import com.indigobyte.reboothealth.agent.domain.AgentTriggerType;
import com.indigobyte.reboothealth.audit.application.AuditLogAppender;
import com.indigobyte.reboothealth.device.domain.DevicePrincipal;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import com.indigobyte.reboothealth.idempotency.application.IdempotencyApplicationService;
import com.indigobyte.reboothealth.idempotency.application.IdempotencyStart;
import com.indigobyte.reboothealth.idempotency.domain.IdempotencyRecord;
import com.indigobyte.reboothealth.idempotency.domain.IdempotencyState;
import java.time.Clock;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * AgentRun 应用服务。
 *
 * <p>负责创建运行、查询状态和接入幂等；Python Runtime 调用由事务提交后的后台 Worker 执行。</p>
 */
@Service
@RequiredArgsConstructor
public class AgentRunApplicationService {

    private static final String RESOURCE_TYPE = "AGENT_RUN";
    private static final String ENTITY_TYPE = "AgentRun";

    private final AgentRunRepository repository;
    private final IdempotencyApplicationService idempotencyService;
    private final AuditLogAppender auditLogAppender;
    private final ObjectMapper objectMapper;
    private final Clock clock;
    private final ApplicationEventPublisher eventPublisher;

    @Transactional
    public IdempotentAgentRunResult create(String idempotencyKey, DevicePrincipal principal, CreateAgentRunCommand command) {
        IdempotencyStart start = idempotencyService.start(idempotencyKey, "AGENT_RUN_CREATE",
                Map.of("deviceId", principal.deviceId()), command);
        if (!start.newRequest()) {
            IdempotencyRecord record = start.existingRecord();
            if (record.getState() != IdempotencyState.COMPLETED) {
                throw new ApplicationException(ErrorCode.DATA_CONFLICT, "幂等请求仍在处理中，请稍后重试", HttpStatus.CONFLICT);
            }
            return new IdempotentAgentRunResult(get(record.getResourceId(), principal), record.getResponseStatus(), true);
        }

        Instant now = Instant.now(clock);
        AgentRun run = AgentRun.create(principal.userId(), principal.deviceId(), command.sessionId(),
                command.triggerType(), command.inputSummary(), now);
        repository.insert(run);
        auditLogAppender.append("AGENT_RUN_CREATED", ENTITY_TYPE, run.getId(), null, redactedRun(run));
        idempotencyService.complete(idempotencyKey, RESOURCE_TYPE, run.getId(), HttpStatus.ACCEPTED.value());
        eventPublisher.publishEvent(new AgentRunCreatedEvent(run.getId(), command.mockMode()));
        return new IdempotentAgentRunResult(toDetail(run), HttpStatus.ACCEPTED.value(), false);
    }

    @Transactional(readOnly = true)
    public AgentRunDetail get(UUID runId, DevicePrincipal principal) {
        AgentRun run = repository.findById(runId)
                .orElseThrow(() -> new ApplicationException(ErrorCode.AGENT_RUN_NOT_FOUND,
                        "AgentRun 不存在", HttpStatus.NOT_FOUND));
        if (!run.getUserId().equals(principal.userId())) {
            throw new ApplicationException(ErrorCode.AGENT_RUN_NOT_FOUND, "AgentRun 不存在", HttpStatus.NOT_FOUND);
        }
        return toDetail(run);
    }

    private AgentRunDetail toDetail(AgentRun run) {
        return new AgentRunDetail(
                run.getId(),
                run.getUserId(),
                run.getDeviceId(),
                run.getSessionId(),
                run.getTriggerType(),
                run.getStatus(),
                run.getInputSummary(),
                readJson(run.getStructuredOutput()),
                readJson(run.getValidationResult()),
                run.getFailureCode(),
                run.getFailureMessage(),
                run.getCreatedAt(),
                run.getStartedAt(),
                run.getCompletedAt(),
                run.getUpdatedAt()
        );
    }

    private JsonNode readJson(String value) {
        if (value == null) {
            return null;
        }
        try {
            return objectMapper.readTree(value);
        } catch (JsonProcessingException ex) {
            throw new ApplicationException(ErrorCode.INTERNAL_ERROR, "AgentRun JSON 读取失败", HttpStatus.INTERNAL_SERVER_ERROR);
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

    public record CreateAgentRunCommand(UUID sessionId, AgentTriggerType triggerType,
                                        String inputSummary, String mockMode) {
    }

    public record IdempotentAgentRunResult(AgentRunDetail body, int responseStatus, boolean replayed) {
    }

}
