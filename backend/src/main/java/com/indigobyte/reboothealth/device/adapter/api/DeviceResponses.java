package com.indigobyte.reboothealth.device.adapter.api;

import com.indigobyte.reboothealth.device.application.DeviceApplicationService.BootstrapStatusView;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService.DeviceAuthResult;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService.DeviceView;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService.PairingSessionView;
import java.time.Instant;
import java.util.UUID;

/**
 * 设备认证 REST 响应 DTO 集合。
 */
public final class DeviceResponses {

    private DeviceResponses() {
    }

    public record BootstrapStatusResponse(boolean initialized) {
        static BootstrapStatusResponse from(BootstrapStatusView view) {
            return new BootstrapStatusResponse(view.initialized());
        }
    }

    public record DeviceAuthResponse(
            UUID userId,
            UUID deviceId,
            String accessToken,
            Instant accessTokenExpiresAt,
            String refreshToken,
            Instant refreshTokenExpiresAt
    ) {
        static DeviceAuthResponse from(DeviceAuthResult result) {
            return new DeviceAuthResponse(
                    result.userId(),
                    result.deviceId(),
                    result.credentials().accessToken(),
                    result.credentials().accessTokenExpiresAt(),
                    result.credentials().refreshToken(),
                    result.credentials().refreshTokenExpiresAt()
            );
        }
    }

    public record PairingSessionResponse(UUID pairingSessionId, String pairingCode,
                                         String qrPayload, Instant expiresAt) {
        static PairingSessionResponse from(PairingSessionView view) {
            return new PairingSessionResponse(view.pairingSessionId(), view.pairingCode(),
                    view.qrPayload(), view.expiresAt());
        }
    }

    public record DeviceResponse(UUID id, String deviceName, String platform, String status,
                                 String trustLevel, Instant createdAt, Instant lastSeenAt,
                                 Instant revokedAt) {
        static DeviceResponse from(DeviceView view) {
            return new DeviceResponse(view.id(), view.deviceName(), view.platform().name(),
                    view.status(), view.trustLevel(), view.createdAt(), view.lastSeenAt(),
                    view.revokedAt());
        }
    }
}
