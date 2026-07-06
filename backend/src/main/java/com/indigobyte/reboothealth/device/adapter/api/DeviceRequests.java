package com.indigobyte.reboothealth.device.adapter.api;

import com.indigobyte.reboothealth.device.domain.DevicePlatform;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/**
 * 设备认证 REST 请求 DTO 集合。
 */
public final class DeviceRequests {

    private DeviceRequests() {
    }

    public record BootstrapConsumeRequest(
            @NotBlank @Size(max = 128) String bootstrapCode,
            @NotBlank @Size(max = 100) String deviceName,
            @NotNull DevicePlatform platform
    ) {
    }

    public record PairingConsumeRequest(
            @NotBlank @Size(max = 128) String pairingCode,
            @NotBlank @Size(max = 100) String deviceName,
            @NotNull DevicePlatform platform
    ) {
    }

    public record RefreshCredentialRequest(
            @NotBlank @Size(max = 256) String refreshToken
    ) {
    }
}
