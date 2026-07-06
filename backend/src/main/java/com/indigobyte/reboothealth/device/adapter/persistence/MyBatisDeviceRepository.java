package com.indigobyte.reboothealth.device.adapter.persistence;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.indigobyte.reboothealth.device.domain.AppUser;
import com.indigobyte.reboothealth.device.domain.BootstrapSession;
import com.indigobyte.reboothealth.device.domain.Device;
import com.indigobyte.reboothealth.device.domain.DeviceCredential;
import com.indigobyte.reboothealth.device.domain.DeviceRepository;
import com.indigobyte.reboothealth.device.domain.PairingSession;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

/**
 * DeviceRepository 的 MyBatis-Plus 实现。
 */
@Repository
@RequiredArgsConstructor
public class MyBatisDeviceRepository implements DeviceRepository {

    private final AppUserMapper appUserMapper;
    private final BootstrapSessionMapper bootstrapSessionMapper;
    private final DeviceMapper deviceMapper;
    private final DeviceCredentialMapper credentialMapper;
    private final PairingSessionMapper pairingSessionMapper;

    @Override
    public Optional<AppUser> findCurrentUser() {
        LambdaQueryWrapper<AppUserDataObject> query = new LambdaQueryWrapper<>();
        query.eq(AppUserDataObject::getSingletonKey, (short) 1);
        return Optional.ofNullable(DevicePersistenceConverter.toDomain(appUserMapper.selectOne(query)));
    }

    @Override
    public void insertUser(AppUser user) {
        appUserMapper.insert(DevicePersistenceConverter.toDataObject(user));
    }

    @Override
    public Optional<BootstrapSession> findActiveBootstrapForUpdate() {
        return Optional.ofNullable(DevicePersistenceConverter.toDomain(bootstrapSessionMapper.selectActiveForUpdate()));
    }

    @Override
    public Optional<BootstrapSession> findBootstrapByHashForUpdate(String codeHash) {
        return Optional.ofNullable(DevicePersistenceConverter.toDomain(
                bootstrapSessionMapper.selectByHashForUpdate(codeHash)));
    }

    @Override
    public void insertBootstrap(BootstrapSession session) {
        bootstrapSessionMapper.insert(DevicePersistenceConverter.toDataObject(session));
    }

    @Override
    public boolean updateBootstrap(BootstrapSession session) {
        return bootstrapSessionMapper.updateById(DevicePersistenceConverter.toDataObject(session)) == 1;
    }

    @Override
    public void insertDevice(Device device) {
        deviceMapper.insert(DevicePersistenceConverter.toDataObject(device));
    }

    @Override
    public boolean updateDevice(Device device) {
        return deviceMapper.updateById(DevicePersistenceConverter.toDataObject(device)) == 1;
    }

    @Override
    public Optional<Device> findDeviceById(UUID deviceId) {
        return Optional.ofNullable(DevicePersistenceConverter.toDomain(deviceMapper.selectById(deviceId)));
    }

    @Override
    public Optional<Device> findDeviceByIdForUpdate(UUID deviceId) {
        return Optional.ofNullable(DevicePersistenceConverter.toDomain(deviceMapper.selectByIdForUpdate(deviceId)));
    }

    @Override
    public List<Device> findDevices(UUID userId) {
        LambdaQueryWrapper<DeviceDataObject> query = new LambdaQueryWrapper<>();
        query.eq(DeviceDataObject::getUserId, userId)
                .orderByDesc(DeviceDataObject::getCreatedAt);
        return deviceMapper.selectList(query).stream()
                .map(DevicePersistenceConverter::toDomain)
                .toList();
    }

    @Override
    public void insertCredential(DeviceCredential credential) {
        credentialMapper.insert(DevicePersistenceConverter.toDataObject(credential));
    }

    @Override
    public boolean updateCredential(DeviceCredential credential) {
        return credentialMapper.updateById(DevicePersistenceConverter.toDataObject(credential)) == 1;
    }

    @Override
    public Optional<DeviceCredential> findCredentialByAccessHash(String accessTokenHash) {
        LambdaQueryWrapper<DeviceCredentialDataObject> query = new LambdaQueryWrapper<>();
        query.eq(DeviceCredentialDataObject::getAccessTokenHash, accessTokenHash);
        return Optional.ofNullable(DevicePersistenceConverter.toDomain(credentialMapper.selectOne(query)));
    }

    @Override
    public Optional<DeviceCredential> findCredentialByRefreshHashForUpdate(String refreshTokenHash) {
        return Optional.ofNullable(DevicePersistenceConverter.toDomain(
                credentialMapper.selectByRefreshHashForUpdate(refreshTokenHash)));
    }

    @Override
    public Optional<DeviceCredential> findCredentialByDeviceIdForUpdate(UUID deviceId) {
        return Optional.ofNullable(DevicePersistenceConverter.toDomain(
                credentialMapper.selectByDeviceIdForUpdate(deviceId)));
    }

    @Override
    public void insertPairingSession(PairingSession session) {
        pairingSessionMapper.insert(DevicePersistenceConverter.toDataObject(session));
    }

    @Override
    public boolean updatePairingSession(PairingSession session) {
        return pairingSessionMapper.updateById(DevicePersistenceConverter.toDataObject(session)) == 1;
    }

    @Override
    public Optional<PairingSession> findPairingByHashForUpdate(String codeHash) {
        return Optional.ofNullable(DevicePersistenceConverter.toDomain(
                pairingSessionMapper.selectByHashForUpdate(codeHash)));
    }
}
