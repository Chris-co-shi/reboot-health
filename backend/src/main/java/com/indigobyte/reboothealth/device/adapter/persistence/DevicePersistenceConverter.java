package com.indigobyte.reboothealth.device.adapter.persistence;

import com.indigobyte.reboothealth.device.domain.AppUser;
import com.indigobyte.reboothealth.device.domain.BootstrapSession;
import com.indigobyte.reboothealth.device.domain.BootstrapStatus;
import com.indigobyte.reboothealth.device.domain.CredentialResponseEnvelope;
import com.indigobyte.reboothealth.device.domain.Device;
import com.indigobyte.reboothealth.device.domain.DeviceCredential;
import com.indigobyte.reboothealth.device.domain.DevicePlatform;
import com.indigobyte.reboothealth.device.domain.DeviceStatus;
import com.indigobyte.reboothealth.device.domain.DeviceTrustLevel;
import com.indigobyte.reboothealth.device.domain.PairingSession;
import com.indigobyte.reboothealth.device.domain.PairingStatus;

/**
 * Device 模块领域对象与持久化对象转换器。
 *
 * <p>枚举统一用 name/valueOf 显式转换，避免依赖 MyBatis 隐式枚举行为。</p>
 */
public final class DevicePersistenceConverter {

    private DevicePersistenceConverter() {
    }

    public static AppUser toDomain(AppUserDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new AppUser(dataObject.getId(), dataObject.getStatus(),
                dataObject.getCreatedAt(), dataObject.getUpdatedAt());
    }

    public static AppUserDataObject toDataObject(AppUser user) {
        AppUserDataObject dataObject = new AppUserDataObject();
        dataObject.setId(user.getId());
        dataObject.setSingletonKey((short) 1);
        dataObject.setStatus(user.getStatus());
        dataObject.setCreatedAt(user.getCreatedAt());
        dataObject.setUpdatedAt(user.getUpdatedAt());
        return dataObject;
    }

    public static BootstrapSession toDomain(BootstrapSessionDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new BootstrapSession(dataObject.getId(), dataObject.getCodeHash(),
                BootstrapStatus.valueOf(dataObject.getStatus()), dataObject.getExpiresAt(),
                dataObject.getConsumedAt(), dataObject.getRevokedAt(), dataObject.getFailureCount(),
                dataObject.getCreatedAt(), dataObject.getUpdatedAt());
    }

    public static BootstrapSessionDataObject toDataObject(BootstrapSession session) {
        BootstrapSessionDataObject dataObject = new BootstrapSessionDataObject();
        dataObject.setId(session.getId());
        dataObject.setCodeHash(session.getCodeHash());
        dataObject.setStatus(session.getStatus().name());
        dataObject.setExpiresAt(session.getExpiresAt());
        dataObject.setConsumedAt(session.getConsumedAt());
        dataObject.setRevokedAt(session.getRevokedAt());
        dataObject.setFailureCount(session.getFailureCount());
        dataObject.setCreatedAt(session.getCreatedAt());
        dataObject.setUpdatedAt(session.getUpdatedAt());
        return dataObject;
    }

    public static Device toDomain(DeviceDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new Device(dataObject.getId(), dataObject.getUserId(), dataObject.getDeviceName(),
                DevicePlatform.valueOf(dataObject.getPlatform()), DeviceStatus.valueOf(dataObject.getStatus()),
                DeviceTrustLevel.valueOf(dataObject.getTrustLevel()), dataObject.getCreatedAt(),
                dataObject.getLastSeenAt(), dataObject.getRevokedAt(), dataObject.getUpdatedAt());
    }

    public static DeviceDataObject toDataObject(Device device) {
        DeviceDataObject dataObject = new DeviceDataObject();
        dataObject.setId(device.getId());
        dataObject.setUserId(device.getUserId());
        dataObject.setDeviceName(device.getDeviceName());
        dataObject.setPlatform(device.getPlatform().name());
        dataObject.setStatus(device.getStatus().name());
        dataObject.setTrustLevel(device.getTrustLevel().name());
        dataObject.setCreatedAt(device.getCreatedAt());
        dataObject.setLastSeenAt(device.getLastSeenAt());
        dataObject.setRevokedAt(device.getRevokedAt());
        dataObject.setUpdatedAt(device.getUpdatedAt());
        return dataObject;
    }

    public static DeviceCredential toDomain(DeviceCredentialDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new DeviceCredential(dataObject.getId(), dataObject.getDeviceId(),
                dataObject.getAccessTokenHash(), dataObject.getAccessTokenExpiresAt(),
                dataObject.getRefreshTokenHash(), dataObject.getRefreshTokenExpiresAt(),
                dataObject.getRefreshTokenRotatedAt(), dataObject.getRevokedAt(),
                dataObject.getCreatedAt(), dataObject.getUpdatedAt());
    }

    public static DeviceCredentialDataObject toDataObject(DeviceCredential credential) {
        DeviceCredentialDataObject dataObject = new DeviceCredentialDataObject();
        dataObject.setId(credential.getId());
        dataObject.setDeviceId(credential.getDeviceId());
        dataObject.setAccessTokenHash(credential.getAccessTokenHash());
        dataObject.setAccessTokenExpiresAt(credential.getAccessTokenExpiresAt());
        dataObject.setRefreshTokenHash(credential.getRefreshTokenHash());
        dataObject.setRefreshTokenExpiresAt(credential.getRefreshTokenExpiresAt());
        dataObject.setRefreshTokenRotatedAt(credential.getRefreshTokenRotatedAt());
        dataObject.setRevokedAt(credential.getRevokedAt());
        dataObject.setCreatedAt(credential.getCreatedAt());
        dataObject.setUpdatedAt(credential.getUpdatedAt());
        return dataObject;
    }

    public static PairingSession toDomain(PairingSessionDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new PairingSession(dataObject.getId(), dataObject.getUserId(),
                dataObject.getCreatedByDeviceId(), dataObject.getCodeHash(),
                PairingStatus.valueOf(dataObject.getStatus()), dataObject.getExpiresAt(),
                dataObject.getConsumedAt(), dataObject.getCancelledAt(), dataObject.getCreatedDeviceId(),
                dataObject.getCreatedAt(), dataObject.getUpdatedAt());
    }

    public static PairingSessionDataObject toDataObject(PairingSession session) {
        PairingSessionDataObject dataObject = new PairingSessionDataObject();
        dataObject.setId(session.getId());
        dataObject.setUserId(session.getUserId());
        dataObject.setCreatedByDeviceId(session.getCreatedByDeviceId());
        dataObject.setCodeHash(session.getCodeHash());
        dataObject.setStatus(session.getStatus().name());
        dataObject.setExpiresAt(session.getExpiresAt());
        dataObject.setConsumedAt(session.getConsumedAt());
        dataObject.setCancelledAt(session.getCancelledAt());
        dataObject.setCreatedDeviceId(session.getCreatedDeviceId());
        dataObject.setCreatedAt(session.getCreatedAt());
        dataObject.setUpdatedAt(session.getUpdatedAt());
        return dataObject;
    }

    public static CredentialResponseEnvelope toDomain(CredentialResponseEnvelopeDataObject dataObject) {
        if (dataObject == null) {
            return null;
        }
        return new CredentialResponseEnvelope(dataObject.getId(), dataObject.getOperationType(),
                dataObject.getIdempotencyKey(), dataObject.getRequestHash(), dataObject.getEncryptedResponse(),
                dataObject.getNonce(), dataObject.getEncryptionKeyVersion(), dataObject.getExpiresAt(),
                dataObject.getCreatedAt());
    }

    public static CredentialResponseEnvelopeDataObject toDataObject(CredentialResponseEnvelope envelope) {
        CredentialResponseEnvelopeDataObject dataObject = new CredentialResponseEnvelopeDataObject();
        dataObject.setId(envelope.getId());
        dataObject.setOperationType(envelope.getOperationType());
        dataObject.setIdempotencyKey(envelope.getIdempotencyKey());
        dataObject.setRequestHash(envelope.getRequestHash());
        dataObject.setEncryptedResponse(envelope.getEncryptedResponse());
        dataObject.setNonce(envelope.getNonce());
        dataObject.setEncryptionKeyVersion(envelope.getEncryptionKeyVersion());
        dataObject.setExpiresAt(envelope.getExpiresAt());
        dataObject.setCreatedAt(envelope.getCreatedAt());
        return dataObject;
    }
}
