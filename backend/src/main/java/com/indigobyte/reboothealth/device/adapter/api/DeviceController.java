package com.indigobyte.reboothealth.device.adapter.api;

import com.indigobyte.reboothealth.device.adapter.api.DeviceRequests.BootstrapConsumeRequest;
import com.indigobyte.reboothealth.device.adapter.api.DeviceRequests.PairingConsumeRequest;
import com.indigobyte.reboothealth.device.adapter.api.DeviceRequests.RefreshCredentialRequest;
import com.indigobyte.reboothealth.device.adapter.api.DeviceResponses.BootstrapStatusResponse;
import com.indigobyte.reboothealth.device.adapter.api.DeviceResponses.DeviceAuthResponse;
import com.indigobyte.reboothealth.device.adapter.api.DeviceResponses.DeviceResponse;
import com.indigobyte.reboothealth.device.adapter.api.DeviceResponses.PairingSessionResponse;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService.BootstrapConsumeCommand;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService.PairingConsumeCommand;
import com.indigobyte.reboothealth.device.application.DeviceApplicationService.RefreshCredentialCommand;
import com.indigobyte.reboothealth.device.domain.DevicePrincipal;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/**
 * 设备 bootstrap、配对、凭据刷新和撤销 API。
 */
@RestController
@RequestMapping("/api/v1")
public class DeviceController {

    private final DeviceApplicationService service;

    public DeviceController(DeviceApplicationService service) {
        this.service = service;
    }

    @GetMapping("/device-bootstrap/status")
    public BootstrapStatusResponse bootstrapStatus() {
        return BootstrapStatusResponse.from(service.bootstrapStatus());
    }

    @PostMapping("/device-bootstrap/consume")
    public ResponseEntity<DeviceAuthResponse> consumeBootstrap(
            @Valid @RequestBody BootstrapConsumeRequest request
    ) {
        DeviceAuthResponse response = DeviceAuthResponse.from(service.consumeBootstrap(
                new BootstrapConsumeCommand(request.bootstrapCode(), request.deviceName(), request.platform())
        ));
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @PostMapping("/devices/pairing-sessions")
    public ResponseEntity<PairingSessionResponse> createPairingSession(
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        DevicePrincipal principal = service.authenticate(authorizationHeader);
        return ResponseEntity.status(HttpStatus.CREATED).body(PairingSessionResponse.from(
                service.createPairingSession(principal)
        ));
    }

    @PostMapping("/devices/pair")
    public ResponseEntity<DeviceAuthResponse> consumePairing(@Valid @RequestBody PairingConsumeRequest request) {
        DeviceAuthResponse response = DeviceAuthResponse.from(service.consumePairing(
                new PairingConsumeCommand(request.pairingCode(), request.deviceName(), request.platform())
        ));
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping("/devices")
    public List<DeviceResponse> listDevices(
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        DevicePrincipal principal = service.authenticate(authorizationHeader);
        return service.listDevices(principal).stream()
                .map(DeviceResponse::from)
                .toList();
    }

    @PostMapping("/devices/{deviceId}/revoke")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void revokeDevice(
            @PathVariable UUID deviceId,
            @RequestHeader(value = "Authorization", required = false) String authorizationHeader
    ) {
        DevicePrincipal principal = service.authenticate(authorizationHeader);
        service.revokeDevice(principal, deviceId);
    }

    @PostMapping("/devices/token/refresh")
    public DeviceAuthResponse refreshCredential(@Valid @RequestBody RefreshCredentialRequest request) {
        return DeviceAuthResponse.from(service.refreshCredential(new RefreshCredentialCommand(request.refreshToken())));
    }
}
