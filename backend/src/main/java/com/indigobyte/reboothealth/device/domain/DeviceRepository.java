package com.indigobyte.reboothealth.device.domain;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 设备认证仓储端口。
 *
 * <p>端口显式表达插入、更新和按摘要查询，避免泄漏 MyBatis 或明文凭据。</p>
 */
public interface DeviceRepository {

    Optional<AppUser> findCurrentUser();

    void insertUser(AppUser user);

    Optional<BootstrapSession> findActiveBootstrapForUpdate();

    Optional<BootstrapSession> findBootstrapByHashForUpdate(String codeHash);

    void insertBootstrap(BootstrapSession session);

    boolean updateBootstrap(BootstrapSession session);

    void insertDevice(Device device);

    boolean updateDevice(Device device);

    Optional<Device> findDeviceById(UUID deviceId);

    Optional<Device> findDeviceByIdForUpdate(UUID deviceId);

    List<Device> findDevices(UUID userId);

    void insertCredential(DeviceCredential credential);

    boolean updateCredential(DeviceCredential credential);

    Optional<DeviceCredential> findCredentialByAccessHash(String accessTokenHash);

    Optional<DeviceCredential> findCredentialByRefreshHashForUpdate(String refreshTokenHash);

    Optional<DeviceCredential> findCredentialByDeviceIdForUpdate(UUID deviceId);

    void insertPairingSession(PairingSession session);

    boolean updatePairingSession(PairingSession session);

    Optional<PairingSession> findPairingByHashForUpdate(String codeHash);
}
