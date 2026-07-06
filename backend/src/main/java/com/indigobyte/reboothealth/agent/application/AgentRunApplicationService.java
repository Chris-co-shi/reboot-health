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
import java.util.List;
import java.util.Map;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * AgentRun 应用服务。
 *
 * <p>负责创建运行、调用 Python Runtime、校验结构化结果、保存状态和接入幂等；不执行任何业务确认命令。</p>
 */
@Service
@RequiredArgsConstructor
public class AgentRunApplicationService {

    private static final String RESOURCE_TYPE = "AGENT_RUN";
    private static final String ENTITY_TYPE = "AgentRun";

    private final AgentRunRepository repository;
    private final AgentRuntimeClient runtimeClient;
    private final IdempotencyApplicationService idempotencyService;
    private final AuditLogAppender auditLogAppender;
    private final ObjectMapper objectMapper;
    private final Clock clock;

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

        run.markRunning(Instant.now(clock));
        repository.update(run);
        try {
            AgentRuntimeResponse response = runtimeClient.execute(new AgentRuntimeRequest(
                    run.getId(),
                    run.getUserId(),
                    run.getDeviceId(),
                    run.getTriggerType().name(),
                    run.getInputSummary(),
                    command.mockMode()
            ));
            run.markValidating(Instant.now(clock));
            repository.update(run);
            ValidationOutcome validation = validate(response);
            run.markReady(toJson(response), toJson(validation), Instant.now(clock));
            repository.update(run);
            auditLogAppender.append("AGENT_RUN_READY_FOR_USER_REVIEW", ENTITY_TYPE,
                    run.getId(), null, redactedRun(run));
        } catch (AgentRuntimeException ex) {
            run.markFailed(ex.code(), sanitize(ex.getMessage()), Instant.now(clock));
            repository.update(run);
            auditLogAppender.append("AGENT_RUN_FAILED", ENTITY_TYPE, run.getId(), null, redactedRun(run));
        } catch (RuntimeException ex) {
            run.markFailed(ErrorCode.AGENT_RUNTIME_UNAVAILABLE.name(), "Agent Runtime 调用失败", Instant.now(clock));
            repository.update(run);
            auditLogAppender.append("AGENT_RUN_FAILED", ENTITY_TYPE, run.getId(), null, redactedRun(run));
        }
        idempotencyService.complete(idempotencyKey, RESOURCE_TYPE, run.getId(), HttpStatus.CREATED.value());
        return new IdempotentAgentRunResult(toDetail(run), HttpStatus.CREATED.value(), false);
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

    private ValidationOutcome validate(AgentRuntimeResponse response) {
        if (response == null
                || !"1.0".equals(response.schemaVersion())
                || response.message() == null
                || response.message().isBlank()
                || response.cards() == null
                || response.cards().isEmpty()) {
            throw new AgentRuntimeException(ErrorCode.AGENT_RUNTIME_INVALID_OUTPUT.name(), "Agent Runtime 输出结构无效");
        }
        for (AgentRuntimeResponse.Card card : response.cards()) {
            if (card.type() == null || card.type().isBlank()
                    || card.title() == null || card.title().isBlank()
                    || card.content() == null || card.content().isBlank()) {
                throw new AgentRuntimeException(ErrorCode.AGENT_RUNTIME_INVALID_OUTPUT.name(), "Agent Runtime 卡片结构无效");
            }
        }
        return new ValidationOutcome(true, List.of());
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

    public record CreateAgentRunCommand(UUID sessionId, AgentTriggerType triggerType,
                                        String inputSummary, String mockMode) {
    }

    public record IdempotentAgentRunResult(AgentRunDetail body, int responseStatus, boolean replayed) {
    }

    private record ValidationOutcome(boolean valid, List<String> issues) {
    }
}
