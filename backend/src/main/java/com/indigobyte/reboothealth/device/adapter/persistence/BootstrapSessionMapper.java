package com.indigobyte.reboothealth.device.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * bootstrap_session 表 Mapper。
 */
@Mapper
public interface BootstrapSessionMapper extends BaseMapper<BootstrapSessionDataObject> {

    /**
     * 锁定当前可用 bootstrap 会话，避免并发消费同一个 code。
     */
    @Select("""
            SELECT id, code_hash, status, expires_at, consumed_at, revoked_at,
                   failure_count, created_at, updated_at
            FROM bootstrap_session
            WHERE status = 'CREATED'
            ORDER BY created_at DESC
            LIMIT 1
            FOR UPDATE
            """)
    BootstrapSessionDataObject selectActiveForUpdate();

    /**
     * 按摘要锁定 bootstrap 会话。
     */
    @Select("""
            SELECT id, code_hash, status, expires_at, consumed_at, revoked_at,
                   failure_count, created_at, updated_at
            FROM bootstrap_session
            WHERE code_hash = #{codeHash}
            FOR UPDATE
            """)
    BootstrapSessionDataObject selectByHashForUpdate(@Param("codeHash") String codeHash);
}
