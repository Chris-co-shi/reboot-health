package com.indigobyte.reboothealth.agent.adapter.api;

import com.indigobyte.reboothealth.agent.domain.AgentTriggerType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.UUID;

/**
 * AgentRun REST 请求 DTO 集合。
 */
public final class AgentRunRequests {

    private AgentRunRequests() {
    }

    public record CreateAgentRunRequest(
            UUID sessionId,
            @NotNull AgentTriggerType triggerType,
            @NotBlank @Size(max = 1000) String inputSummary,
            @Size(max = 32) String mockMode
    ) {
    }
}
