package com.indigobyte.reboothealth.device.application;

import com.indigobyte.reboothealth.audit.application.AuditLogAppender;
import com.indigobyte.reboothealth.device.domain.AppUser;
import com.indigobyte.reboothealth.device.domain.BootstrapSession;
import com.indigobyte.reboothealth.device.domain.Device;
import com.indigobyte.reboothealth.device.domain.DeviceCredential;
import com.indigobyte.reboothealth.device.domain.DevicePlatform;
import com.indigobyte.reboothealth.device.domain.DevicePrincipal;
import com.indigobyte.reboothealth.device.domain.DeviceRepository;
import com.indigobyte.reboothealth.device.domain.IssuedCredentials;
import com.indigobyte.reboothealth.device.domain.PairingSession;
import com.indigobyte.reboothealth.device.domain.TokenPair;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 设备认证应用服务。
 *
 * <p>负责首台设备 bootstrap、后续配对、设备凭据签发/轮换和撤销；不建设注册、密码或角色权限体系。</p>
 */
@Service
@RequiredArgsConstructor
public class DeviceApplicationService {

    private static final String SECURITY_EVENT = "SecurityEvent";

    private final DeviceRepository repository;
    private final DeviceTokenService tokenService;
    private final AuditLogAppender auditLogAppender;
    private final SecurityAuditAppender securityAuditAppender;
    private final Clock clock;

    @Value("${app.device.bootstrap.code-ttl-minutes:10}")
    private long bootstrapCodeTtlMinutes;

    @Value("${app.device.bootstrap.code-length:24}")
    private int bootstrapCodeLength;

    @Value("${app.device.bootstrap.max-failures:5}")
    private int bootstrapMaxFailures;

    @Value("${app.device.pairing.code-ttl-minutes:10}")
    private long pairingCodeTtlMinutes;

    @Value("${app.device.pairing.code-length:16}")
    private int pairingCodeLength;

    /**
     * CLI 专用：生成首台设备 bootstrap code。
     */
    @Transactional
    public BootstrapCode createBootstrapCodeForCli() {
        if (repository.findCurrentUser().isPresent()) {
            throw new ApplicationException(ErrorCode.BOOTSTRAP_NOT_AVAILABLE,
                    "首台设备已初始化，不能再次生成 bootstrap code", HttpStatus.CONFLICT);
        }
        if (repository.findActiveBootstrapForUpdate().isPresent()) {
            throw new ApplicationException(ErrorCode.BOOTSTRAP_NOT_AVAILABLE,
                    "已有未消费的 bootstrap code", HttpStatus.CONFLICT);
        }
        Instant now = Instant.now(clock);
        String code = tokenService.generateCode(bootstrapCodeLength);
        BootstrapSession session = BootstrapSession.create(
                tokenService.hash(code),
                now.plus(Duration.ofMinutes(bootstrapCodeTtlMinutes)),
                now
        );
        repository.insertBootstrap(session);
        auditLogAppender.append("BOOTSTRAP_CODE_CREATED", SECURITY_EVENT, session.getId(), null,
                Map.of("expiresAt", session.getExpiresAt()));
        return new BootstrapCode(code, session.getExpiresAt());
    }

    @Transactional(readOnly = true)
    public BootstrapStatusView bootstrapStatus() {
        return new BootstrapStatusView(repository.findCurrentUser().isPresent());
    }

    /**
     * 首台 Flutter 设备消费 bootstrap code。
     */
    @Transactional(noRollbackFor = BootstrapRejectedException.class)
    public DeviceAuthResult consumeBootstrap(BootstrapConsumeCommand command) {
        Instant now = Instant.now(clock);
        if (repository.findCurrentUser().isPresent()) {
            rejectBootstrap(null, "ALREADY_INITIALIZED");
        }

        String codeHash = tokenService.hash(command.bootstrapCode());
        BootstrapSession session = repository.findBootstrapByHashForUpdate(codeHash).orElse(null);
        if (session == null) {
            repository.findActiveBootstrapForUpdate().ifPresent(active -> {
                active.recordFailure(now);
                if (active.getFailureCount() >= bootstrapMaxFailures) {
                    active.revoke(now);
                }
                repository.updateBootstrap(active);
            });
            rejectBootstrap(null, "INVALID_CODE");
        }
        if (!session.isUsable(now)) {
            if (session.getExpiresAt().isBefore(now) || session.getExpiresAt().equals(now)) {
                session.markExpired(now);
                repository.updateBootstrap(session);
            }
            rejectBootstrap(session.getId(), "EXPIRED_OR_CONSUMED");
        }

        AppUser user = AppUser.create(now);
        Device device = Device.trustedPrimary(user.getId(), command.deviceName(), command.platform(), now);
        TokenPair tokenPair = tokenService.issueTokenPair(now);
        DeviceCredential credential = DeviceCredential.create(device.getId(), tokenPair, now);

        repository.insertUser(user);
        repository.insertDevice(device);
        repository.insertCredential(credential);
        session.markConsumed(now);
        repository.updateBootstrap(session);

        auditLogAppender.append("BOOTSTRAP_CODE_CONSUMED", SECURITY_EVENT, session.getId(), null,
                Map.of("deviceId", device.getId(), "userId", user.getId()));
        auditLogAppender.append("PRIMARY_DEVICE_INITIALIZED", SECURITY_EVENT, device.getId(), null,
                Map.of("userId", user.getId(), "deviceId", device.getId(), "platform", device.getPlatform()));
        return new DeviceAuthResult(user.getId(), device.getId(), tokenPair.issuedCredentials());
    }

    @Transactional
    public DevicePrincipal authenticate(String authorizationHeader) {
        String token = bearerToken(authorizationHeader);
        Instant now = Instant.now(clock);
        DeviceCredential credential = repository.findCredentialByAccessHash(tokenService.hash(token))
                .orElseThrow(() -> unauthorized(ErrorCode.DEVICE_CREDENTIAL_INVALID, "设备凭据无效"));
        if (!credential.isAccessTokenValid(now)) {
            throw unauthorized(ErrorCode.DEVICE_CREDENTIAL_INVALID, "设备访问令牌已过期或已撤销");
        }
        Device device = repository.findDeviceById(credential.getDeviceId())
                .orElseThrow(() -> unauthorized(ErrorCode.DEVICE_NOT_FOUND, "设备不存在"));
        device.ensureActive();
        device.markSeen(now);
        repository.updateDevice(device);
        return new DevicePrincipal(device.getUserId(), device.getId());
    }

    @Transactional
    public PairingSessionView createPairingSession(DevicePrincipal principal) {
        Device device = repository.findDeviceByIdForUpdate(principal.deviceId())
                .orElseThrow(() -> new ApplicationException(ErrorCode.DEVICE_NOT_FOUND, "设备不存在", HttpStatus.NOT_FOUND));
        device.ensureActive();
        Instant now = Instant.now(clock);
        String code = tokenService.generateCode(pairingCodeLength);
        UUID sessionId = UUID.randomUUID();
        String qrPayload = "reboot-health://pair?sessionId=" + sessionId + "&code=" + code;
        PairingSession session = PairingSession.create(principal.userId(), principal.deviceId(),
                tokenService.hash(code), qrPayload, now.plus(Duration.ofMinutes(pairingCodeTtlMinutes)), now);
        session = new PairingSession(sessionId, session.getUserId(), session.getCreatedByDeviceId(),
                session.getCodeHash(), session.getQrPayload(), session.getStatus(), session.getExpiresAt(),
                session.getConsumedAt(), session.getCancelledAt(), session.getCreatedDeviceId(),
                session.getCreatedAt(), session.getUpdatedAt());
        repository.insertPairingSession(session);
        auditLogAppender.append("PAIRING_SESSION_CREATED", SECURITY_EVENT, session.getId(), null,
                Map.of("createdByDeviceId", principal.deviceId(), "expiresAt", session.getExpiresAt()));
        return new PairingSessionView(session.getId(), code, session.getQrPayload(), session.getExpiresAt());
    }

    @Transactional
    public DeviceAuthResult consumePairing(PairingConsumeCommand command) {
        Instant now = Instant.now(clock);
        String codeHash = tokenService.hash(command.pairingCode());
        PairingSession session = repository.findPairingByHashForUpdate(codeHash)
                .orElseThrow(() -> new ApplicationException(ErrorCode.PAIRING_SESSION_INVALID,
                        "配对码无效", HttpStatus.CONFLICT));
        if (!session.isUsable(now)) {
            if (session.getExpiresAt().isBefore(now) || session.getExpiresAt().equals(now)) {
                session.markExpired(now);
                repository.updatePairingSession(session);
                auditLogAppender.append("PAIRING_SESSION_EXPIRED", SECURITY_EVENT, session.getId(), null,
                        Map.of("expiresAt", session.getExpiresAt()));
            }
            throw new ApplicationException(ErrorCode.PAIRING_SESSION_INVALID, "配对码已过期或已使用", HttpStatus.CONFLICT);
        }
        Device device = Device.trusted(session.getUserId(), command.deviceName(), command.platform(), now);
        TokenPair tokenPair = tokenService.issueTokenPair(now);
        DeviceCredential credential = DeviceCredential.create(device.getId(), tokenPair, now);
        repository.insertDevice(device);
        repository.insertCredential(credential);
        session.markConsumed(device.getId(), now);
        repository.updatePairingSession(session);
        auditLogAppender.append("PAIRING_SESSION_CONSUMED", SECURITY_EVENT, session.getId(), null,
                Map.of("createdDeviceId", device.getId(), "userId", session.getUserId()));
        auditLogAppender.append("DEVICE_PAIRED", SECURITY_EVENT, device.getId(), null,
                Map.of("deviceId", device.getId(), "platform", device.getPlatform()));
        return new DeviceAuthResult(session.getUserId(), device.getId(), tokenPair.issuedCredentials());
    }

    @Transactional(readOnly = true)
    public List<DeviceView> listDevices(DevicePrincipal principal) {
        return repository.findDevices(principal.userId()).stream()
                .map(DeviceView::from)
                .toList();
    }

    @Transactional
    public void revokeDevice(DevicePrincipal principal, UUID targetDeviceId) {
        Device target = repository.findDeviceByIdForUpdate(targetDeviceId)
                .orElseThrow(() -> new ApplicationException(ErrorCode.DEVICE_NOT_FOUND, "设备不存在", HttpStatus.NOT_FOUND));
        if (!target.getUserId().equals(principal.userId())) {
            throw new ApplicationException(ErrorCode.DEVICE_NOT_FOUND, "设备不存在", HttpStatus.NOT_FOUND);
        }
        Instant now = Instant.now(clock);
        target.revoke(now);
        repository.updateDevice(target);
        repository.findCredentialByDeviceIdForUpdate(targetDeviceId).ifPresent(credential -> {
            credential.revoke(now);
            repository.updateCredential(credential);
        });
        auditLogAppender.append("DEVICE_REVOKED", SECURITY_EVENT, targetDeviceId, null,
                Map.of("revokedByDeviceId", principal.deviceId(), "deviceId", targetDeviceId));
    }

    @Transactional
    public DeviceAuthResult refreshCredential(RefreshCredentialCommand command) {
        Instant now = Instant.now(clock);
        String refreshHash = tokenService.hash(command.refreshToken());
        DeviceCredential credential = repository.findCredentialByRefreshHashForUpdate(refreshHash)
                .orElseThrow(() -> unauthorized(ErrorCode.DEVICE_CREDENTIAL_INVALID, "刷新凭据无效"));
        if (!credential.isRefreshTokenValid(now)) {
            throw unauthorized(ErrorCode.DEVICE_CREDENTIAL_INVALID, "刷新凭据已过期或已撤销");
        }
        Device device = repository.findDeviceByIdForUpdate(credential.getDeviceId())
                .orElseThrow(() -> unauthorized(ErrorCode.DEVICE_NOT_FOUND, "设备不存在"));
        device.ensureActive();
        TokenPair tokenPair = tokenService.issueTokenPair(now);
        credential.rotate(tokenPair, now);
        device.markSeen(now);
        repository.updateCredential(credential);
        repository.updateDevice(device);
        auditLogAppender.append("DEVICE_TOKEN_REFRESHED", SECURITY_EVENT, device.getId(), null,
                Map.of("deviceId", device.getId()));
        auditLogAppender.append("DEVICE_CREDENTIAL_ROTATED", SECURITY_EVENT, credential.getId(), null,
                Map.of("deviceId", device.getId()));
        return new DeviceAuthResult(device.getUserId(), device.getId(), tokenPair.issuedCredentials());
    }

    private void rejectBootstrap(UUID entityId, String reason) {
        securityAuditAppender.append("BOOTSTRAP_CODE_REJECTED", SECURITY_EVENT,
                entityId == null ? UUID.randomUUID() : entityId,
                null,
                Map.of("reason", reason));
        throw new BootstrapRejectedException();
    }

    private String bearerToken(String authorizationHeader) {
        if (authorizationHeader == null || !authorizationHeader.startsWith("Bearer ")) {
            throw unauthorized(ErrorCode.DEVICE_UNAUTHORIZED, "缺少设备访问令牌");
        }
        String token = authorizationHeader.substring("Bearer ".length()).trim();
        if (token.isBlank()) {
            throw unauthorized(ErrorCode.DEVICE_UNAUTHORIZED, "缺少设备访问令牌");
        }
        return token;
    }

    private ApplicationException unauthorized(ErrorCode code, String message) {
        return new ApplicationException(code, message, HttpStatus.UNAUTHORIZED);
    }

    public record BootstrapCode(String code, Instant expiresAt) {
    }

    public record BootstrapStatusView(boolean initialized) {
    }

    public record BootstrapConsumeCommand(String bootstrapCode, String deviceName, DevicePlatform platform) {
    }

    public record PairingConsumeCommand(String pairingCode, String deviceName, DevicePlatform platform) {
    }

    public record RefreshCredentialCommand(String refreshToken) {
    }

    public record DeviceAuthResult(UUID userId, UUID deviceId, IssuedCredentials credentials) {
    }

    public record PairingSessionView(UUID pairingSessionId, String pairingCode, String qrPayload, Instant expiresAt) {
    }

    public record DeviceView(UUID id, String deviceName, DevicePlatform platform, String status,
                             String trustLevel, Instant createdAt, Instant lastSeenAt, Instant revokedAt) {
        public static DeviceView from(Device device) {
            return new DeviceView(device.getId(), device.getDeviceName(), device.getPlatform(),
                    device.getStatus().name(), device.getTrustLevel().name(), device.getCreatedAt(),
                    device.getLastSeenAt(), device.getRevokedAt());
        }
    }
}
