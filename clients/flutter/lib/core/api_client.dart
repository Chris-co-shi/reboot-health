import 'dart:convert';
import 'dart:math';

import 'package:http/http.dart' as http;

import '../features/auth/secure_credential_store.dart';
import 'app_config.dart';

class ApiException implements Exception {
  const ApiException(this.statusCode, this.message);

  final int statusCode;
  final String message;
}

class ApiClient {
  ApiClient({
    required AppConfig config,
    required CredentialStore credentialStore,
    http.Client? httpClient,
  })  : _config = config,
        _credentialStore = credentialStore,
        _httpClient = httpClient ?? http.Client();

  final AppConfig _config;
  final CredentialStore _credentialStore;
  final http.Client _httpClient;
  final Random _random = Random.secure();
  Future<bool>? _refreshInFlight;

  String createIdempotencyKey() {
    final List<int> bytes = List<int>.generate(16, (_) => _random.nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final String hex = bytes.map((int byte) => byte.toRadixString(16).padLeft(2, '0')).join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-'
        '${hex.substring(16, 20)}-${hex.substring(20)}';
  }

  Future<Map<String, Object?>> getJson(String path, {bool authorized = false}) async {
    return _request('GET', path, authorized: authorized);
  }

  Future<Map<String, Object?>> postJson(
    String path, {
    Map<String, Object?> body = const <String, Object?>{},
    bool authorized = false,
    String? idempotencyKey,
  }) async {
    return _request(
      'POST',
      path,
      body: body,
      authorized: authorized,
      idempotencyKey: idempotencyKey,
    );
  }

  Uri _uri(String path) {
    return Uri.parse('${_config.apiBaseUrl}$path');
  }

  Future<Map<String, Object?>> _request(
    String method,
    String path, {
    Map<String, Object?> body = const <String, Object?>{},
    required bool authorized,
    String? idempotencyKey,
    bool allowRefresh = true,
  }) async {
    final http.Response response = await _send(
      method,
      path,
      body: body,
      authorized: authorized,
      idempotencyKey: idempotencyKey,
    );
    if (response.statusCode == 401 && authorized && allowRefresh) {
      final bool refreshed = await _refreshCredentials();
      if (refreshed) {
        final http.Response retry = await _send(
          method,
          path,
          body: body,
          authorized: authorized,
          idempotencyKey: idempotencyKey,
        );
        return _decode(retry);
      }
    }
    return _decode(response);
  }

  Future<http.Response> _send(
    String method,
    String path, {
    required Map<String, Object?> body,
    required bool authorized,
    String? idempotencyKey,
  }) async {
    final Map<String, String> headers = await _headers(authorized: authorized);
    if (idempotencyKey != null) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    final Uri uri = _uri(path);
    if (method == 'GET') {
      return _httpClient.get(uri, headers: headers);
    }
    return _httpClient.post(uri, headers: headers, body: jsonEncode(body));
  }

  Future<Map<String, String>> _headers({required bool authorized}) async {
    final Map<String, String> headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (authorized) {
      final DeviceCredentials? credentials = await _credentialStore.read();
      if (credentials != null) {
        headers['Authorization'] = 'Bearer ${credentials.accessToken}';
      }
    }
    return headers;
  }

  Map<String, Object?> _decode(http.Response response) {
    final Object? value = response.body.isEmpty ? <String, Object?>{} : jsonDecode(response.body);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return value is Map<String, Object?> ? value : <String, Object?>{};
    }
    String message = '请求失败，请稍后重试';
    if (value is Map<String, Object?> && value['message'] is String) {
      message = value['message'] as String;
    }
    throw ApiException(response.statusCode, message);
  }

  Future<bool> _refreshCredentials() {
    final Future<bool>? existing = _refreshInFlight;
    if (existing != null) {
      return existing;
    }
    final Future<bool> future = _performRefresh();
    _refreshInFlight = future;
    future.whenComplete(() => _refreshInFlight = null);
    return future;
  }

  Future<bool> _performRefresh() async {
    final DeviceCredentials? current = await _credentialStore.read();
    if (current == null) {
      return false;
    }
    final http.Response response = await _send(
      'POST',
      '/api/v1/devices/token/refresh',
      body: <String, Object?>{'refreshToken': current.refreshToken},
      authorized: false,
      idempotencyKey: createIdempotencyKey(),
    );
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final Map<String, Object?> json = _decode(response);
      await _credentialStore.save(DeviceCredentials(
        userId: json['userId'] as String,
        deviceId: json['deviceId'] as String,
        accessToken: json['accessToken'] as String,
        refreshToken: json['refreshToken'] as String,
      ));
      return true;
    }
    await _credentialStore.clear();
    return false;
  }
}
