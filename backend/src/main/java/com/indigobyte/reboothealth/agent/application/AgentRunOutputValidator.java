package com.indigobyte.reboothealth.agent.application;

import java.util.List;
import org.springframework.stereotype.Component;

/**
 * Agent Runtime 输出结构校验器。
 *
 * <p>M2.5-A 只接受固定 schemaVersion 和可展示卡片，避免未校验的模型输出进入 AgentRun。</p>
 */
@Component
public class AgentRunOutputValidator {

    public ValidationOutcome validate(AgentRuntimeResponse response) {
        if (response == null
                || !"1.0".equals(response.schemaVersion())
                || response.message() == null
                || response.message().isBlank()
                || response.cards() == null
                || response.cards().isEmpty()) {
            throw new AgentRuntimeException("AGENT_RUNTIME_INVALID_OUTPUT", "Agent Runtime 输出结构无效");
        }
        for (AgentRuntimeResponse.Card card : response.cards()) {
            if (card.type() == null || card.type().isBlank()
                    || card.title() == null || card.title().isBlank()
                    || card.content() == null || card.content().isBlank()) {
                throw new AgentRuntimeException("AGENT_RUNTIME_INVALID_OUTPUT", "Agent Runtime 卡片结构无效");
            }
        }
        return new ValidationOutcome(true, List.of());
    }

    public record ValidationOutcome(boolean valid, List<String> issues) {
    }
}
