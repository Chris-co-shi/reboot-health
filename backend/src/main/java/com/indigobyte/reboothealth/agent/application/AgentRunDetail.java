package com.indigobyte.reboothealth.agent.application;

import com.fasterxml.jackson.databind.JsonNode;
import com.indigobyte.reboothealth.agent.domain.AgentRunStatus;
import com.indigobyte.reboothealth.agent.domain.AgentTriggerType;
import java.time.Instant;
import java.util.UUID;

/**
 * AgentRun 查询详情。
 */
public record AgentRunDetail(
        UUID id,
        UUID userId,
        UUID deviceId,
        UUID sessionId,
        AgentTriggerType triggerType,
        AgentRunStatus status,
        String inputSummary,
        JsonNode structuredOutput,
        JsonNode validationResult,
        String failureCode,
        String failureMessage,
        Instant createdAt,
        Instant startedAt,
        Instant completedAt,
        Instant updatedAt
) {
}
