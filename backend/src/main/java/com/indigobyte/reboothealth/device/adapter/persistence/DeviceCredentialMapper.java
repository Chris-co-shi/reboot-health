package com.indigobyte.reboothealth.device.adapter.persistence;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import java.util.UUID;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * device_credential 表 Mapper。
 */
@Mapper
public interface DeviceCredentialMapper extends BaseMapper<DeviceCredentialDataObject> {

    /**
     * 按 refresh credential 摘要锁定凭据，用于安全轮换。
     */
    @Select("""
            SELECT id, device_id, access_token_hash, access_token_expires_at,
                   refresh_token_hash, refresh_token_expires_at, refresh_token_rotated_at,
                   revoked_at, created_at, updated_at
            FROM device_credential
            WHERE refresh_token_hash = #{refreshTokenHash}
            FOR UPDATE
            """)
    DeviceCredentialDataObject selectByRefreshHashForUpdate(@Param("refreshTokenHash") String refreshTokenHash);

    /**
     * 按设备锁定凭据，用于撤销设备时同步撤销凭据。
     */
    @Select("""
            SELECT id, device_id, access_token_hash, access_token_expires_at,
                   refresh_token_hash, refresh_token_expires_at, refresh_token_rotated_at,
                   revoked_at, created_at, updated_at
            FROM device_credential
            WHERE device_id = #{deviceId}
            FOR UPDATE
            """)
    DeviceCredentialDataObject selectByDeviceIdForUpdate(@Param("deviceId") UUID deviceId);
}
