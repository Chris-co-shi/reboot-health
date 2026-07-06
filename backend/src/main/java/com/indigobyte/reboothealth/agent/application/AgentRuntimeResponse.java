package com.indigobyte.reboothealth.agent.application;

import java.util.List;

/**
 * Python Agent Runtime 返回的结构化结果。
 */
public record AgentRuntimeResponse(
        String schemaVersion,
        String message,
        List<Card> cards
) {

    /**
     * 用户可见卡片。
     */
    public record Card(String type, String title, String content) {
    }
}
