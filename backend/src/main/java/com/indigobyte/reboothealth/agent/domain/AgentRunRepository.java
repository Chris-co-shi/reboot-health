package com.indigobyte.reboothealth.agent.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * AgentRun 仓储端口。
 */
public interface AgentRunRepository {

    Optional<AgentRun> findById(UUID runId);

    Optional<AgentRun> findByIdForUpdate(UUID runId);

    void insert(AgentRun run);

    boolean update(AgentRun run);

    int expireStaleRuns(java.time.Instant staleBefore, java.time.Instant now);

    void insertToolCall(AgentToolCall toolCall);

    List<AgentToolCall> findToolCalls(UUID runId);
}
