import '../../core/api_client.dart';
import 'secure_credential_store.dart';

class DeviceAuthApi {
  const DeviceAuthApi(this._client, this._credentialStore);

  final ApiClient _client;
  final CredentialStore _credentialStore;

  Future<DeviceCredentials> consumeBootstrap({
    required String bootstrapCode,
    required String deviceName,
    required String platform,
  }) async {
    final Map<String, Object?> json = await _client.postJson(
      '/api/v1/device-bootstrap/consume',
      body: <String, Object?>{
        'bootstrapCode': bootstrapCode,
        'deviceName': deviceName,
        'platform': platform,
      },
    );
    final DeviceCredentials credentials = _credentialsFrom(json);
    await _credentialStore.save(credentials);
    return credentials;
  }

  Future<PairingSessionView> createPairingSession() async {
    final Map<String, Object?> json = await _client.postJson(
      '/api/v1/devices/pairing-sessions',
      authorized: true,
    );
    return PairingSessionView.fromJson(json);
  }

  Future<DeviceCredentials> consumePairing({
    required String pairingCode,
    required String deviceName,
    required String platform,
  }) async {
    final Map<String, Object?> json = await _client.postJson(
      '/api/v1/devices/pair',
      body: <String, Object?>{
        'pairingCode': pairingCode,
        'deviceName': deviceName,
        'platform': platform,
      },
    );
    final DeviceCredentials credentials = _credentialsFrom(json);
    await _credentialStore.save(credentials);
    return credentials;
  }

  Future<List<DeviceView>> listDevices() async {
    final Map<String, Object?> json = await _client.getJson('/api/v1/devices', authorized: true);
    final Object? items = json['items'];
    if (items is! List<Object?>) {
      return const <DeviceView>[];
    }
    return items.whereType<Map<String, Object?>>().map(DeviceView.fromJson).toList();
  }

  DeviceCredentials _credentialsFrom(Map<String, Object?> json) {
    return DeviceCredentials(
      userId: json['userId'] as String,
      deviceId: json['deviceId'] as String,
      accessToken: json['accessToken'] as String,
      refreshToken: json['refreshToken'] as String,
    );
  }
}

class PairingSessionView {
  const PairingSessionView({
    required this.pairingSessionId,
    required this.pairingCode,
    required this.qrPayload,
    required this.expiresAt,
  });

  factory PairingSessionView.fromJson(Map<String, Object?> json) {
    return PairingSessionView(
      pairingSessionId: json['pairingSessionId'] as String,
      pairingCode: json['pairingCode'] as String,
      qrPayload: json['qrPayload'] as String,
      expiresAt: DateTime.parse(json['expiresAt'] as String),
    );
  }

  final String pairingSessionId;
  final String pairingCode;
  final String qrPayload;
  final DateTime expiresAt;
}

class DeviceView {
  const DeviceView({
    required this.id,
    required this.deviceName,
    required this.platform,
    required this.status,
    required this.trustLevel,
  });

  factory DeviceView.fromJson(Map<String, Object?> json) {
    return DeviceView(
      id: json['id'] as String,
      deviceName: json['deviceName'] as String,
      platform: json['platform'] as String,
      status: json['status'] as String,
      trustLevel: json['trustLevel'] as String,
    );
  }

  final String id;
  final String deviceName;
  final String platform;
  final String status;
  final String trustLevel;
}
