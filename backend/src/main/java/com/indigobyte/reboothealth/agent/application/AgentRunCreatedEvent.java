package com.indigobyte.reboothealth.agent.application;

import java.util.UUID;

/**
 * AgentRun 创建提交后的异步执行事件。
 */
public record AgentRunCreatedEvent(UUID runId, String mockMode) {
}
