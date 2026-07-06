package com.indigobyte.reboothealth.device.adapter.persistence;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;

/**
 * credential_response_envelope 表持久化对象。
 */
@Getter
@Setter
@TableName("credential_response_envelope")
public class CredentialResponseEnvelopeDataObject {

    @TableId(type = IdType.INPUT)
    private UUID id;
    private String operationType;
    private String idempotencyKey;
    private String requestHash;
    private String encryptedResponse;
    private String nonce;
    private String encryptionKeyVersion;
    private Instant expiresAt;
    private Instant createdAt;
}
