package com.indigobyte.reboothealth.idempotency.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import java.time.Instant;
import java.util.UUID;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Update;

/**
 * idempotency_record 表 Mapper。
 */
@Mapper
public interface IdempotencyRecordMapper extends BaseMapper<IdempotencyRecordDataObject> {

    @Insert("""
            INSERT INTO idempotency_record (
                id, idempotency_key, operation_code, request_hash, state,
                resource_type, resource_id, response_status, created_at, completed_at
            ) VALUES (
                #{id}, #{idempotencyKey}, #{operationCode}, #{requestHash}, #{state},
                #{resourceType}, #{resourceId}, #{responseStatus}, #{createdAt}, #{completedAt}
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            """)
    int insertProcessing(IdempotencyRecordDataObject dataObject);

    @Update("""
            UPDATE idempotency_record
            SET state = 'COMPLETED',
                resource_type = #{resourceType},
                resource_id = #{resourceId},
                response_status = #{responseStatus},
                completed_at = #{completedAt}
            WHERE idempotency_key = #{key} AND state = 'PROCESSING'
            """)
    int complete(@Param("key") String key,
                 @Param("resourceType") String resourceType,
                 @Param("resourceId") UUID resourceId,
                 @Param("responseStatus") int responseStatus,
                 @Param("completedAt") Instant completedAt);

    @Delete("""
            DELETE FROM idempotency_record
            WHERE idempotency_key = #{key} AND state = 'PROCESSING'
            """)
    int deleteProcessing(@Param("key") String key);
}
