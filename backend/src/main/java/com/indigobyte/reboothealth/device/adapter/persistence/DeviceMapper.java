package com.indigobyte.reboothealth.device.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import java.util.UUID;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * device 表 Mapper。
 */
@Mapper
public interface DeviceMapper extends BaseMapper<DeviceDataObject> {

    /**
     * 按 id 锁定设备，用于撤销和凭据刷新流程。
     */
    @Select("""
            SELECT id, user_id, device_name, platform, status, trust_level,
                   created_at, last_seen_at, revoked_at, updated_at
            FROM device
            WHERE id = #{deviceId}
            FOR UPDATE
            """)
    DeviceDataObject selectByIdForUpdate(@Param("deviceId") UUID deviceId);

    /**
     * 锁定当前主设备，用于显式主设备转移。
     */
    @Select("""
            SELECT id, user_id, device_name, platform, status, trust_level,
                   created_at, last_seen_at, revoked_at, updated_at
            FROM device
            WHERE user_id = #{userId}
              AND trust_level = 'TRUSTED_PRIMARY'
            FOR UPDATE
            """)
    DeviceDataObject selectPrimaryForUpdate(@Param("userId") UUID userId);
}
