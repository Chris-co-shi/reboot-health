package com.indigobyte.reboothealth.device.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;

/**
 * device 表持久化对象。
 */
@Getter
@Setter
@TableName("device")
public class DeviceDataObject {

    @TableId(type = IdType.INPUT)
    private UUID id;
    private UUID userId;
    private String deviceName;
    private String platform;
    private String status;
    private String trustLevel;
    private Instant createdAt;
    private Instant lastSeenAt;
    private Instant revokedAt;
    private Instant updatedAt;
}
