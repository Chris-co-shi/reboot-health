package com.indigobyte.reboothealth.device.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * pairing_session 表 Mapper。
 */
@Mapper
public interface PairingSessionMapper extends BaseMapper<PairingSessionDataObject> {

    /**
     * 按摘要锁定配对会话，用于一次性消费。
     */
    @Select("""
            SELECT id, user_id, created_by_device_id, code_hash, status,
                   expires_at, consumed_at, cancelled_at, created_device_id,
                   created_at, updated_at
            FROM pairing_session
            WHERE code_hash = #{codeHash}
            FOR UPDATE
            """)
    PairingSessionDataObject selectByHashForUpdate(@Param("codeHash") String codeHash);
}
