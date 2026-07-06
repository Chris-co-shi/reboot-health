package com.indigobyte.reboothealth.agent.adapter.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.indigobyte.reboothealth.agent.application.AgentRunDetail;
import java.time.Instant;
import java.util.UUID;

/**
 * AgentRun REST 响应。
 */
public record AgentRunResponse(
        UUID id,
        String triggerType,
        String status,
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

    public static AgentRunResponse from(AgentRunDetail detail) {
        return new AgentRunResponse(
                detail.id(),
                detail.triggerType().name(),
                detail.status().name(),
                detail.inputSummary(),
                detail.structuredOutput(),
                detail.validationResult(),
                detail.failureCode(),
                detail.failureMessage(),
                detail.createdAt(),
                detail.startedAt(),
                detail.completedAt(),
                detail.updatedAt()
        );
    }
}
