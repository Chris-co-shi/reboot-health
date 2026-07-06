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

  String createIdempotencyKey() {
    final int a = _random.nextInt(1 << 32);
    final int b = _random.nextInt(1 << 32);
    return 'flutter-${DateTime.now().microsecondsSinceEpoch}-$a-$b';
  }

  Future<Map<String, Object?>> getJson(String path, {bool authorized = false}) async {
    final http.Response response = await _httpClient.get(
      _uri(path),
      headers: await _headers(authorized: authorized),
    );
    return _decode(response);
  }

  Future<Map<String, Object?>> postJson(
    String path, {
    Map<String, Object?> body = const <String, Object?>{},
    bool authorized = false,
    String? idempotencyKey,
  }) async {
    final Map<String, String> headers = await _headers(authorized: authorized);
    if (idempotencyKey != null) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    final http.Response response = await _httpClient.post(
      _uri(path),
      headers: headers,
      body: jsonEncode(body),
    );
    return _decode(response);
  }

  Uri _uri(String path) {
    return Uri.parse('${_config.apiBaseUrl}$path');
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
}
