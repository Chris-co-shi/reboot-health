package com.indigobyte.reboothealth.device.domain;

import java.time.Instant;

/**
 * 返回给设备端的一次性明文凭据。
 *
 * <p>该对象只用于 API 响应，不进入审计快照和日志。</p>
 */
public record IssuedCredentials(
        String accessToken,
        Instant accessTokenExpiresAt,
        String refreshToken,
        Instant refreshTokenExpiresAt
) {
}
