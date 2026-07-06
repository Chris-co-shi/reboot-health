import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reboot_health/core/api_client.dart';
import 'package:reboot_health/core/app_config.dart';
import 'package:reboot_health/core/idempotent_action.dart';
import 'package:reboot_health/features/auth/secure_credential_store.dart';

void main() {
  test('401 后 refresh 成功并重试原请求一次', () async {
    final InMemoryCredentialStore store = InMemoryCredentialStore()
      ..value = const DeviceCredentials(
        userId: 'user-1',
        deviceId: 'device-1',
        accessToken: 'old-access',
        refreshToken: 'old-refresh',
      );
    int protectedCalls = 0;
    int refreshCalls = 0;
    final ApiClient apiClient = ApiClient(
      config: const AppConfig(apiBaseUrl: 'http://127.0.0.1:8080'),
      credentialStore: store,
      httpClient: MockClient((http.Request request) async {
        if (request.url.path == '/api/v1/devices/token/refresh') {
          refreshCalls++;
          return http.Response(
            '{"userId":"user-1","deviceId":"device-1","accessToken":"new-access","refreshToken":"new-refresh"}',
            201,
          );
        }
        protectedCalls++;
        if (protectedCalls == 1) {
          return http.Response('{"message":"expired"}', 401);
        }
        return http.Response('{"ok":true}', 200);
      }),
    );

    final Map<String, Object?> result = await apiClient.getJson('/api/v1/protected', authorized: true);

    expect(result['ok'], true);
    expect(refreshCalls, 1);
    expect(protectedCalls, 2);
    expect((await store.read())?.accessToken, 'new-access');
  });

  test('并发 401 只触发一次 refresh', () async {
    final InMemoryCredentialStore store = InMemoryCredentialStore()
      ..value = const DeviceCredentials(
        userId: 'user-1',
        deviceId: 'device-1',
        accessToken: 'old-access',
        refreshToken: 'old-refresh',
      );
    final Completer<void> refreshStarted = Completer<void>();
    final Completer<void> allowRefresh = Completer<void>();
    bool refreshed = false;
    int refreshCalls = 0;
    final ApiClient apiClient = ApiClient(
      config: const AppConfig(apiBaseUrl: 'http://127.0.0.1:8080'),
      credentialStore: store,
      httpClient: MockClient((http.Request request) async {
        if (request.url.path == '/api/v1/devices/token/refresh') {
          refreshCalls++;
          refreshStarted.complete();
          await allowRefresh.future;
          refreshed = true;
          return http.Response(
            '{"userId":"user-1","deviceId":"device-1","accessToken":"new-access","refreshToken":"new-refresh"}',
            201,
          );
        }
        return refreshed ? http.Response('{"ok":true}', 200) : http.Response('{"message":"expired"}', 401);
      }),
    );

    final Future<List<Map<String, Object?>>> calls = Future.wait(<Future<Map<String, Object?>>>[
      apiClient.getJson('/api/v1/protected-a', authorized: true),
      apiClient.getJson('/api/v1/protected-b', authorized: true),
    ]);
    await refreshStarted.future;
    allowRefresh.complete();
    final List<Map<String, Object?>> results = await calls;

    expect(results.map((Map<String, Object?> result) => result['ok']), everyElement(true));
    expect(refreshCalls, 1);
  });

  test('refresh 失败会清除凭据', () async {
    final InMemoryCredentialStore store = InMemoryCredentialStore()
      ..value = const DeviceCredentials(
        userId: 'user-1',
        deviceId: 'device-1',
        accessToken: 'old-access',
        refreshToken: 'old-refresh',
      );
    final ApiClient apiClient = ApiClient(
      config: const AppConfig(apiBaseUrl: 'http://127.0.0.1:8080'),
      credentialStore: store,
      httpClient: MockClient((http.Request request) async {
        if (request.url.path == '/api/v1/devices/token/refresh') {
          return http.Response('{"message":"invalid"}', 401);
        }
        return http.Response('{"message":"expired"}', 401);
      }),
    );

    expect(() => apiClient.getJson('/api/v1/protected', authorized: true), throwsA(isA<ApiException>()));
    expect(await store.read(), isNull);
  });

  test('幂等 action 在网络错误和 5xx 后保留 key，在明确 4xx 后清除 key', () async {
    int sequence = 0;
    final IdempotentAction action = IdempotentAction(() => 'key-${++sequence}');

    await expectLater(action.run<void>((String _) async => throw const ApiException(500, 'server')), throwsA(isA<ApiException>()));
    expect(action.key, 'key-1');

    await expectLater(action.run<void>((String _) async => throw const ApiException(400, 'bad')), throwsA(isA<ApiException>()));
    expect(action.key, 'key-2');
  });
}

class InMemoryCredentialStore implements CredentialStore {
  DeviceCredentials? value;

  @override
  Future<void> clear() async {
    value = null;
  }

  @override
  Future<DeviceCredentials?> read() async {
    return value;
  }

  @override
  Future<void> save(DeviceCredentials credentials) async {
    value = credentials;
  }
}
