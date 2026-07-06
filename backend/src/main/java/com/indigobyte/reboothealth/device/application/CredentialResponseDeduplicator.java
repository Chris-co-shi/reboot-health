package com.indigobyte.reboothealth.device.application;

import com.indigobyte.reboothealth.device.domain.CredentialResponseEnvelope;
import com.indigobyte.reboothealth.device.domain.DeviceRepository;
import com.indigobyte.reboothealth.device.domain.IssuedCredentials;
import com.indigobyte.reboothealth.error.ApplicationException;
import com.indigobyte.reboothealth.error.ErrorCode;
import com.indigobyte.reboothealth.idempotency.application.IdempotencyApplicationService;
import com.indigobyte.reboothealth.idempotency.application.IdempotencyStart;
import com.indigobyte.reboothealth.idempotency.domain.IdempotencyRecord;
import com.indigobyte.reboothealth.idempotency.domain.IdempotencyState;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.function.Supplier;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

/**
 * 设备凭据响应的幂等编排器。
 *
 * <p>普通幂等表不保存响应体；涉及明文凭据的接口需要额外保存加密信封，才能在同 key 重放时返回第一次签发的同一组凭据。</p>
 */
@Service
@RequiredArgsConstructor
public class CredentialResponseDeduplicator {

    private static final String RESOURCE_TYPE = "DEVICE_CREDENTIAL_RESPONSE";

    private final IdempotencyApplicationService idempotencyService;
    private final DeviceRepository repository;
    private final CredentialResponseCrypto crypto;
    private final Clock clock;

    @Value("${app.device.credential-envelope.replay-ttl-minutes:30}")
    private long replayTtlMinutes;

    public CredentialIdempotentResult execute(String idempotencyKey, String operationCode,
                                              Map<String, UUID> pathIds, Object command,
                                              Supplier<DeviceApplicationService.DeviceAuthResult> action) {
        IdempotencyStart start = idempotencyService.start(idempotencyKey, operationCode, pathIds, command);
        if (!start.newRequest()) {
            IdempotencyRecord record = start.existingRecord();
            if (record.getState() != IdempotencyState.COMPLETED) {
                throw new ApplicationException(ErrorCode.DATA_CONFLICT, "幂等请求仍在处理中，请稍后重试", HttpStatus.CONFLICT);
            }
            CredentialResponseEnvelope envelope = repository.findCredentialResponseEnvelopeByKey(idempotencyKey)
                    .orElseThrow(() -> new ApplicationException(ErrorCode.CREDENTIAL_RESPONSE_REPLAY_UNAVAILABLE,
                            "设备凭据幂等响应不存在", HttpStatus.CONFLICT));
            CredentialReplayPayload payload = crypto.decrypt(envelope, CredentialReplayPayload.class, Instant.now(clock));
            return new CredentialIdempotentResult(payload.toResult(), record.getResponseStatus(), true);
        }

        try {
            DeviceApplicationService.DeviceAuthResult result = action.get();
            Instant now = Instant.now(clock);
            CredentialReplayPayload payload = CredentialReplayPayload.from(result);
            CredentialResponseCrypto.EncryptedCredentialResponse encrypted = crypto.encrypt(payload);
            repository.insertCredentialResponseEnvelope(CredentialResponseEnvelope.create(
                    operationCode,
                    idempotencyKey,
                    start.requestHash(),
                    encrypted.encryptedResponse(),
                    encrypted.nonce(),
                    encrypted.keyVersion(),
                    now.plus(Duration.ofMinutes(replayTtlMinutes)),
                    now
            ));
            idempotencyService.complete(idempotencyKey, RESOURCE_TYPE, result.deviceId(), HttpStatus.CREATED.value());
            return new CredentialIdempotentResult(result, HttpStatus.CREATED.value(), false);
        } catch (RuntimeException ex) {
            idempotencyService.discardProcessing(idempotencyKey);
            throw ex;
        }
    }

    public record CredentialIdempotentResult(DeviceApplicationService.DeviceAuthResult body,
                                             int responseStatus,
                                             boolean replayed) {
    }

    public record CredentialReplayPayload(UUID userId,
                                          UUID deviceId,
                                          String accessToken,
                                          Instant accessTokenExpiresAt,
                                          String refreshToken,
                                          Instant refreshTokenExpiresAt) {
        static CredentialReplayPayload from(DeviceApplicationService.DeviceAuthResult result) {
            IssuedCredentials credentials = result.credentials();
            return new CredentialReplayPayload(result.userId(), result.deviceId(),
                    credentials.accessToken(), credentials.accessTokenExpiresAt(),
                    credentials.refreshToken(), credentials.refreshTokenExpiresAt());
        }

        DeviceApplicationService.DeviceAuthResult toResult() {
            return new DeviceApplicationService.DeviceAuthResult(userId, deviceId,
                    new IssuedCredentials(accessToken, accessTokenExpiresAt, refreshToken, refreshTokenExpiresAt));
        }
    }
}
