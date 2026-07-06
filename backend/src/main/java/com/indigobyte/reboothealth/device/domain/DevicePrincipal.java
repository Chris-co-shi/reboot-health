package com.indigobyte.reboothealth.device.domain;

import java.util.UUID;

/**
 * 已通过设备 access token 认证的调用方。
 */
public record DevicePrincipal(UUID userId, UUID deviceId) {
}
