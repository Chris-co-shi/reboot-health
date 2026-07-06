package com.indigobyte.reboothealth.device.application;

import com.indigobyte.reboothealth.device.domain.TokenPair;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * 设备 code 和 token 生成、摘要工具。
 *
 * <p>服务端只保存 SHA-256 摘要；明文值只返回给调用方一次，不进入日志和审计。</p>
 */
@Component
public class DeviceTokenService {

    private static final String ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

    private final SecureRandom secureRandom = new SecureRandom();
    private final Duration accessTokenTtl;
    private final Duration refreshTokenTtl;

    public DeviceTokenService(
            @Value("${app.device.access-token-ttl-minutes:30}") long accessTokenTtlMinutes,
            @Value("${app.device.refresh-token-ttl-days:30}") long refreshTokenTtlDays
    ) {
        this.accessTokenTtl = Duration.ofMinutes(accessTokenTtlMinutes);
        this.refreshTokenTtl = Duration.ofDays(refreshTokenTtlDays);
    }

    public String generateCode(int length) {
        StringBuilder builder = new StringBuilder(length);
        for (int index = 0; index < length; index++) {
            builder.append(ALPHABET.charAt(secureRandom.nextInt(ALPHABET.length())));
        }
        return builder.toString();
    }

    public String generateOpaqueToken() {
        byte[] bytes = new byte[32];
        secureRandom.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    public TokenPair issueTokenPair(Instant now) {
        String accessToken = generateOpaqueToken();
        String refreshToken = generateOpaqueToken();
        return new TokenPair(
                accessToken,
                hash(accessToken),
                now.plus(accessTokenTtl),
                refreshToken,
                hash(refreshToken),
                now.plus(refreshTokenTtl)
        );
    }

    public String hash(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder(bytes.length * 2);
            for (byte b : bytes) {
                builder.append(String.format("%02x", b));
            }
            return builder.toString();
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 不可用", ex);
        }
    }
}
