import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class DeviceCredentials {
  const DeviceCredentials({
    required this.userId,
    required this.deviceId,
    required this.accessToken,
    required this.refreshToken,
  });

  final String userId;
  final String deviceId;
  final String accessToken;
  final String refreshToken;
}

abstract interface class CredentialStore {
  Future<DeviceCredentials?> read();

  Future<void> save(DeviceCredentials credentials);

  Future<void> clear();
}

class SecureCredentialStore implements CredentialStore {
  SecureCredentialStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  static const String _userIdKey = 'reboot_health_user_id';
  static const String _deviceIdKey = 'reboot_health_device_id';
  static const String _accessTokenKey = 'reboot_health_access_token';
  static const String _refreshTokenKey = 'reboot_health_refresh_token';

  final FlutterSecureStorage _storage;

  @override
  Future<DeviceCredentials?> read() async {
    final String? userId = await _storage.read(key: _userIdKey);
    final String? deviceId = await _storage.read(key: _deviceIdKey);
    final String? accessToken = await _storage.read(key: _accessTokenKey);
    final String? refreshToken = await _storage.read(key: _refreshTokenKey);
    if (userId == null || deviceId == null || accessToken == null || refreshToken == null) {
      return null;
    }
    return DeviceCredentials(
      userId: userId,
      deviceId: deviceId,
      accessToken: accessToken,
      refreshToken: refreshToken,
    );
  }

  @override
  Future<void> save(DeviceCredentials credentials) async {
    await _storage.write(key: _userIdKey, value: credentials.userId);
    await _storage.write(key: _deviceIdKey, value: credentials.deviceId);
    await _storage.write(key: _accessTokenKey, value: credentials.accessToken);
    await _storage.write(key: _refreshTokenKey, value: credentials.refreshToken);
  }

  @override
  Future<void> clear() async {
    await _storage.delete(key: _userIdKey);
    await _storage.delete(key: _deviceIdKey);
    await _storage.delete(key: _accessTokenKey);
    await _storage.delete(key: _refreshTokenKey);
  }
}
