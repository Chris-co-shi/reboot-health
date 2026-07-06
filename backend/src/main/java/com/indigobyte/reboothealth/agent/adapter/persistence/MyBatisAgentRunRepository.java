package com.indigobyte.reboothealth.agent.adapter.persistence;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.indigobyte.reboothealth.agent.domain.AgentRun;
import com.indigobyte.reboothealth.agent.domain.AgentRunRepository;
import com.indigobyte.reboothealth.agent.domain.AgentToolCall;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

/**
 * AgentRunRepository 的 MyBatis-Plus 实现。
 */
@Repository
@RequiredArgsConstructor
public class MyBatisAgentRunRepository implements AgentRunRepository {

    private final AgentRunMapper agentRunMapper;
    private final AgentToolCallMapper toolCallMapper;

    @Override
    public Optional<AgentRun> findById(UUID runId) {
        return Optional.ofNullable(AgentPersistenceConverter.toDomain(agentRunMapper.selectById(runId)));
    }

    @Override
    public void insert(AgentRun run) {
        agentRunMapper.insertAgentRun(AgentPersistenceConverter.toDataObject(run));
    }

    @Override
    public boolean update(AgentRun run) {
        return agentRunMapper.updateAgentRun(AgentPersistenceConverter.toDataObject(run)) == 1;
    }

    @Override
    public void insertToolCall(AgentToolCall toolCall) {
        toolCallMapper.insert(AgentPersistenceConverter.toDataObject(toolCall));
    }

    @Override
    public List<AgentToolCall> findToolCalls(UUID runId) {
        LambdaQueryWrapper<AgentToolCallDataObject> query = new LambdaQueryWrapper<>();
        query.eq(AgentToolCallDataObject::getRunId, runId)
                .orderByAsc(AgentToolCallDataObject::getCreatedAt);
        return toolCallMapper.selectList(query).stream()
                .map(AgentPersistenceConverter::toDomain)
                .toList();
    }
}
