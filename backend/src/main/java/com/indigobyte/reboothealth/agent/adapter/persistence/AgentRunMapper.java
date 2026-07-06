package com.indigobyte.reboothealth.agent.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Update;

/**
 * agent_run 表 Mapper。
 *
 * <p>structured_output 和 validation_result 是 JSONB，写入时显式 CAST，避免隐式字符串映射风险。</p>
 */
@Mapper
public interface AgentRunMapper extends BaseMapper<AgentRunDataObject> {

    @Insert("""
            INSERT INTO agent_run (
                id, user_id, device_id, session_id, trigger_type, status,
                input_summary, structured_output, validation_result, failure_code, failure_message,
                created_at, started_at, completed_at, updated_at
            ) VALUES (
                #{id}, #{userId}, #{deviceId}, #{sessionId}, #{triggerType}, #{status},
                #{inputSummary}, CAST(#{structuredOutput} AS jsonb), CAST(#{validationResult} AS jsonb),
                #{failureCode}, #{failureMessage}, #{createdAt}, #{startedAt}, #{completedAt}, #{updatedAt}
            )
            """)
    int insertAgentRun(AgentRunDataObject dataObject);

    @Update("""
            UPDATE agent_run
            SET status = #{status},
                structured_output = CAST(#{structuredOutput} AS jsonb),
                validation_result = CAST(#{validationResult} AS jsonb),
                failure_code = #{failureCode},
                failure_message = #{failureMessage},
                started_at = #{startedAt},
                completed_at = #{completedAt},
                updated_at = #{updatedAt}
            WHERE id = #{id}
            """)
    int updateAgentRun(AgentRunDataObject dataObject);
}
