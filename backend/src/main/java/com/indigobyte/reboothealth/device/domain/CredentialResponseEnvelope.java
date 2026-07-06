package com.indigobyte.reboothealth.device.domain;

import java.time.Instant;
import java.util.UUID;

/**
 * 设备凭据类接口的加密响应信封。
 *
 * <p>它只服务于幂等重放：数据库保存加密后的响应体和请求指纹，不保存明文 access token 或 refresh credential。</p>
 */
public class CredentialResponseEnvelope {

    private final UUID id;
    private final String operationType;
    private final String idempotencyKey;
    private final String requestHash;
    private final String encryptedResponse;
    private final String nonce;
    private final String encryptionKeyVersion;
    private final Instant expiresAt;
    private final Instant createdAt;

    public CredentialResponseEnvelope(UUID id, String operationType, String idempotencyKey, String requestHash,
                                      String encryptedResponse, String nonce, String encryptionKeyVersion,
                                      Instant expiresAt, Instant createdAt) {
        this.id = id;
        this.operationType = operationType;
        this.idempotencyKey = idempotencyKey;
        this.requestHash = requestHash;
        this.encryptedResponse = encryptedResponse;
        this.nonce = nonce;
        this.encryptionKeyVersion = encryptionKeyVersion;
        this.expiresAt = expiresAt;
        this.createdAt = createdAt;
    }

    public static CredentialResponseEnvelope create(String operationType, String idempotencyKey, String requestHash,
                                                    String encryptedResponse, String nonce,
                                                    String encryptionKeyVersion, Instant expiresAt, Instant now) {
        return new CredentialResponseEnvelope(UUID.randomUUID(), operationType, idempotencyKey, requestHash,
                encryptedResponse, nonce, encryptionKeyVersion, expiresAt, now);
    }

    public boolean isReplayable(Instant now) {
        return expiresAt.isAfter(now);
    }

    public UUID getId() {
        return id;
    }

    public String getOperationType() {
        return operationType;
    }

    public String getIdempotencyKey() {
        return idempotencyKey;
    }

    public String getRequestHash() {
        return requestHash;
    }

    public String getEncryptedResponse() {
        return encryptedResponse;
    }

    public String getNonce() {
        return nonce;
    }

    public String getEncryptionKeyVersion() {
        return encryptionKeyVersion;
    }

    public Instant getExpiresAt() {
        return expiresAt;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
