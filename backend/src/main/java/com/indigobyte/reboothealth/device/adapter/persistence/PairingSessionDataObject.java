package com.indigobyte.reboothealth.device.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;

/**
 * pairing_session 表持久化对象。
 */
@Getter
@Setter
@TableName("pairing_session")
public class PairingSessionDataObject {

    @TableId(type = IdType.INPUT)
    private UUID id;
    private UUID userId;
    private UUID createdByDeviceId;
    private String codeHash;
    private String qrPayload;
    private String status;
    private Instant expiresAt;
    private Instant consumedAt;
    private Instant cancelledAt;
    private UUID createdDeviceId;
    private Instant createdAt;
    private Instant updatedAt;
}
