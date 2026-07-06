package com.indigobyte.reboothealth.device.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;

/**
 * bootstrap_session 表持久化对象。
 */
@Getter
@Setter
@TableName("bootstrap_session")
public class BootstrapSessionDataObject {

    @TableId(type = IdType.INPUT)
    private UUID id;
    private String codeHash;
    private String status;
    private Instant expiresAt;
    private Instant consumedAt;
    private Instant revokedAt;
    private Integer failureCount;
    private Instant createdAt;
    private Instant updatedAt;
}
