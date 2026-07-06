package com.indigobyte.reboothealth.agent.application;

import java.util.UUID;

/**
 * 提交给 Python Agent Runtime 的最小请求。
 */
public record AgentRuntimeRequest(
        UUID runId,
        UUID userId,
        UUID deviceId,
        String triggerType,
        String inputSummary,
        String mockMode
) {
}
