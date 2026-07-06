package com.indigobyte.reboothealth.agent.adapter.persistence;

import com.indigobyte.reboothealth.agent.domain.AgentRun;
import com.indigobyte.reboothealth.agent.domain.AgentRunStatus;
import com.indigobyte.reboothealth.agent.domain.AgentToolCall;
import com.indigobyte.reboothealth.agent.domain.AgentToolCallStatus;
import com.indigobyte.reboothealth.agent.domain.AgentToolPermissionLevel;
import com.indigobyte.reboothealth.agent.domain.AgentTriggerType;

/**
 * Agent 模块领域对象与持久化对象转换器。
 */
public final class AgentPersistenceConverter {

    private AgentPersistenceConverter() {
    }

    public static AgentRun toDomain(AgentRunDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new AgentRun(dataObject.getId(), dataObject.getUserId(), dataObject.getDeviceId(),
                dataObject.getSessionId(), AgentTriggerType.valueOf(dataObject.getTriggerType()),
                AgentRunStatus.valueOf(dataObject.getStatus()), dataObject.getInputSummary(),
                dataObject.getStructuredOutput(), dataObject.getValidationResult(),
                dataObject.getFailureCode(), dataObject.getFailureMessage(), dataObject.getCreatedAt(),
                dataObject.getStartedAt(), dataObject.getCompletedAt(), dataObject.getUpdatedAt());
    }

    public static AgentRunDataObject toDataObject(AgentRun run) {
        AgentRunDataObject dataObject = new AgentRunDataObject();
        dataObject.setId(run.getId());
        dataObject.setUserId(run.getUserId());
        dataObject.setDeviceId(run.getDeviceId());
        dataObject.setSessionId(run.getSessionId());
        dataObject.setTriggerType(run.getTriggerType().name());
        dataObject.setStatus(run.getStatus().name());
        dataObject.setInputSummary(run.getInputSummary());
        dataObject.setStructuredOutput(run.getStructuredOutput());
        dataObject.setValidationResult(run.getValidationResult());
        dataObject.setFailureCode(run.getFailureCode());
        dataObject.setFailureMessage(run.getFailureMessage());
        dataObject.setCreatedAt(run.getCreatedAt());
        dataObject.setStartedAt(run.getStartedAt());
        dataObject.setCompletedAt(run.getCompletedAt());
        dataObject.setUpdatedAt(run.getUpdatedAt());
        return dataObject;
    }

    public static AgentToolCall toDomain(AgentToolCallDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new AgentToolCall(dataObject.getId(), dataObject.getRunId(), dataObject.getToolName(),
                AgentToolPermissionLevel.valueOf(dataObject.getPermissionLevel()),
                dataObject.getArgumentSummary(), dataObject.getResultSummary(),
                AgentToolCallStatus.valueOf(dataObject.getStatus()), dataObject.getLatencyMs(),
                dataObject.getErrorCode(), dataObject.getCreatedAt());
    }

    public static AgentToolCallDataObject toDataObject(AgentToolCall toolCall) {
        AgentToolCallDataObject dataObject = new AgentToolCallDataObject();
        dataObject.setId(toolCall.id());
        dataObject.setRunId(toolCall.runId());
        dataObject.setToolName(toolCall.toolName());
        dataObject.setPermissionLevel(toolCall.permissionLevel().name());
        dataObject.setArgumentSummary(toolCall.argumentSummary());
        dataObject.setResultSummary(toolCall.resultSummary());
        dataObject.setStatus(toolCall.status().name());
        dataObject.setLatencyMs(toolCall.latencyMs());
        dataObject.setErrorCode(toolCall.errorCode());
        dataObject.setCreatedAt(toolCall.createdAt());
        return dataObject;
    }
}
