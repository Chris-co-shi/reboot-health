package com.indigobyte.reboothealth.agent.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;

/**
 * agent_tool_call 表持久化对象。
 */
@Getter
@Setter
@TableName("agent_tool_call")
public class AgentToolCallDataObject {

    @TableId(type = IdType.INPUT)
    private UUID id;
    private UUID runId;
    private String toolName;
    private String permissionLevel;
    private String argumentSummary;
    private String resultSummary;
    private String status;
    private Integer latencyMs;
    private String errorCode;
    private Instant createdAt;
}
