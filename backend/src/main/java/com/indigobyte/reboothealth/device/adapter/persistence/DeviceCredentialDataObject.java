package com.indigobyte.reboothealth.device.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;

/**
 * device_credential 表持久化对象。
 */
@Getter
@Setter
@TableName("device_credential")
public class DeviceCredentialDataObject {

    @TableId(type = IdType.INPUT)
    private UUID id;
    private UUID deviceId;
    private String accessTokenHash;
    private Instant accessTokenExpiresAt;
    private String refreshTokenHash;
    private Instant refreshTokenExpiresAt;
    private Instant refreshTokenRotatedAt;
    private Instant revokedAt;
    private Instant createdAt;
    private Instant updatedAt;
}
