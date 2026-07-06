package com.indigobyte.reboothealth.device.domain;

import java.time.Instant;

/**
 * 设备凭据的明文和摘要组合。
 */
public record TokenPair(
        String accessToken,
        String accessTokenHash,
        Instant accessTokenExpiresAt,
        String refreshToken,
        String refreshTokenHash,
        Instant refreshTokenExpiresAt
) {

    public IssuedCredentials issuedCredentials() {
        return new IssuedCredentials(accessToken, accessTokenExpiresAt, refreshToken, refreshTokenExpiresAt);
    }
}
