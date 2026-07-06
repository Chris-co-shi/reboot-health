package com.indigobyte.reboothealth.agent.domain;

import java.time.Instant;
import java.util.UUID;

/**
 * Agent 工具调用观测记录。
 */
public record AgentToolCall(
        UUID id,
        UUID runId,
        String toolName,
        AgentToolPermissionLevel permissionLevel,
        String argumentSummary,
        String resultSummary,
        AgentToolCallStatus status,
        Integer latencyMs,
        String errorCode,
        Instant createdAt
) {
}
