import 'package:flutter_test/flutter_test.dart';
import 'package:reboot_health/features/auth/secure_credential_store.dart';

void main() {
  test('凭据通过 CredentialStore 抽象访问', () async {
    final InMemoryCredentialStore store = InMemoryCredentialStore();
    const DeviceCredentials credentials = DeviceCredentials(
      userId: 'user-1',
      deviceId: 'device-1',
      accessToken: 'access',
      refreshToken: 'refresh',
    );

    await store.save(credentials);
    expect((await store.read())?.deviceId, 'device-1');

    await store.clear();
    expect(await store.read(), isNull);
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
