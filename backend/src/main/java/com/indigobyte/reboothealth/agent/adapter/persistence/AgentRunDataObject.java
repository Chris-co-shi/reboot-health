package com.indigobyte.reboothealth.agent.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;

/**
 * agent_run 表持久化对象。
 */
@Getter
@Setter
@TableName("agent_run")
public class AgentRunDataObject {

    @TableId(type = IdType.INPUT)
    private UUID id;
    private UUID userId;
    private UUID deviceId;
    private UUID sessionId;
    private String triggerType;
    private String status;
    private String inputSummary;
    private String structuredOutput;
    private String validationResult;
    private String failureCode;
    private String failureMessage;
    private Instant createdAt;
    private Instant startedAt;
    private Instant completedAt;
    private Instant updatedAt;
}
