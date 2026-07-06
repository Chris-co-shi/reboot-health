package com.indigobyte.reboothealth.agent.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import java.time.Instant;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
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

    @Select("""
            SELECT id, user_id, device_id, session_id, trigger_type, status,
                   input_summary, structured_output::text AS structured_output,
                   validation_result::text AS validation_result,
                   failure_code, failure_message, created_at, started_at, completed_at, updated_at
            FROM agent_run
            WHERE id = #{runId}
            FOR UPDATE
            """)
    AgentRunDataObject selectByIdForUpdate(@Param("runId") java.util.UUID runId);

    @Update("""
            UPDATE agent_run
            SET status = 'EXPIRED',
                failure_code = 'EXPIRED',
                failure_message = 'AgentRun 执行超时，已过期',
                completed_at = #{now},
                updated_at = #{now}
            WHERE status IN ('CREATED', 'RUNNING', 'VALIDATING')
              AND updated_at < #{staleBefore}
            """)
    int expireStaleRuns(@Param("staleBefore") Instant staleBefore, @Param("now") Instant now);
}
