import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:reboot_health/core/api_client.dart';
import 'package:reboot_health/core/app_config.dart';
import 'package:reboot_health/features/auth/secure_credential_store.dart';
import 'package:reboot_health/main.dart';

void main() {
  testWidgets('主导航存在且不暴露计划内部概念', (WidgetTester tester) async {
    final CredentialStore store = InMemoryCredentialStore();
    final ApiClient client = ApiClient(
      config: const AppConfig(apiBaseUrl: 'http://127.0.0.1:8080'),
      credentialStore: store,
    );

    await tester.pumpWidget(RebootHealthApp(apiClient: client, credentialStore: store));

    expect(find.text('今日'), findsOneWidget);
    expect(find.text('教练'), findsOneWidget);
    expect(find.text('计划'), findsOneWidget);
    expect(find.text('数据'), findsOneWidget);
    expect(find.text('我的'), findsOneWidget);
    expect(find.textContaining('PlanVersion'), findsNothing);
    expect(find.textContaining('revision'), findsNothing);
    expect(find.textContaining('periodRevision'), findsNothing);
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
