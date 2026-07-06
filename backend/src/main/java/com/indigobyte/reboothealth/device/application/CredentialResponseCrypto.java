package com.indigobyte.reboothealth.device.application;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.indigobyte.reboothealth.device.domain.CredentialResponseEnvelope;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

/**
 * 设备凭据响应信封加解密组件。
 *
 * <p>只负责 AES-GCM 加密幂等重放所需的响应体；密钥必须由环境配置提供，不写入仓库。</p>
 */
@Component
public class CredentialResponseCrypto {

    private static final int NONCE_BYTES = 12;
    private static final int TAG_BITS = 128;

    private final ObjectMapper objectMapper;
    private final SecureRandom secureRandom = new SecureRandom();
    private final String keyBase64;
    private final String keyVersion;

    public CredentialResponseCrypto(
            ObjectMapper objectMapper,
            @Value("${app.device.credential-envelope.key-base64:}") String keyBase64,
            @Value("${app.device.credential-envelope.key-version:local-v1}") String keyVersion
    ) {
        this.objectMapper = objectMapper;
        this.keyBase64 = keyBase64;
        this.keyVersion = keyVersion;
    }

    public EncryptedCredentialResponse encrypt(Object payload) {
        try {
            byte[] nonce = new byte[NONCE_BYTES];
            secureRandom.nextBytes(nonce);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, secretKey(), new GCMParameterSpec(TAG_BITS, nonce));
            byte[] ciphertext = cipher.doFinal(objectMapper.writeValueAsString(payload).getBytes(StandardCharsets.UTF_8));
            return new EncryptedCredentialResponse(
                    Base64.getEncoder().encodeToString(ciphertext),
                    Base64.getEncoder().encodeToString(nonce),
                    keyVersion
            );
        } catch (JsonProcessingException | GeneralSecurityException ex) {
            throw new ApplicationException(ErrorCode.INTERNAL_ERROR, "设备凭据响应加密失败", HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }

    public <T> T decrypt(CredentialResponseEnvelope envelope, Class<T> type, Instant now) {
        if (!envelope.isReplayable(now)) {
            throw new ApplicationException(ErrorCode.CREDENTIAL_RESPONSE_REPLAY_UNAVAILABLE,
                    "设备凭据幂等重放已过期，请重新执行操作", HttpStatus.CONFLICT);
        }
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            byte[] nonce = Base64.getDecoder().decode(envelope.getNonce());
            cipher.init(Cipher.DECRYPT_MODE, secretKey(), new GCMParameterSpec(TAG_BITS, nonce));
            byte[] plaintext = cipher.doFinal(Base64.getDecoder().decode(envelope.getEncryptedResponse()));
            return objectMapper.readValue(new String(plaintext, StandardCharsets.UTF_8), type);
        } catch (JsonProcessingException | GeneralSecurityException | IllegalArgumentException ex) {
            throw new ApplicationException(ErrorCode.CREDENTIAL_RESPONSE_REPLAY_UNAVAILABLE,
                    "设备凭据幂等重放无法恢复", HttpStatus.CONFLICT);
        }
    }

    private SecretKeySpec secretKey() {
        if (keyBase64 == null || keyBase64.isBlank()) {
            throw new ApplicationException(ErrorCode.INTERNAL_ERROR,
                    "设备凭据响应加密密钥未配置", HttpStatus.INTERNAL_SERVER_ERROR);
        }
        byte[] key;
        try {
            key = Base64.getDecoder().decode(keyBase64);
        } catch (IllegalArgumentException ex) {
            throw new ApplicationException(ErrorCode.INTERNAL_ERROR,
                    "设备凭据响应加密密钥格式无效", HttpStatus.INTERNAL_SERVER_ERROR);
        }
        if (key.length != 16 && key.length != 24 && key.length != 32) {
            throw new ApplicationException(ErrorCode.INTERNAL_ERROR,
                    "设备凭据响应加密密钥长度无效", HttpStatus.INTERNAL_SERVER_ERROR);
        }
        return new SecretKeySpec(key, "AES");
    }

    public record EncryptedCredentialResponse(String encryptedResponse, String nonce, String keyVersion) {
    }
}
