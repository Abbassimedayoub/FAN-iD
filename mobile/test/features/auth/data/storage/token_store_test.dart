import 'package:fanid_mobile/features/auth/data/storage/token_store.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  test('keeps access token in memory and stores refresh securely', () async {
    const secureStorage = FlutterSecureStorage();
    final store = TokenStore(secureStorage: secureStorage);

    await store.save(
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
    );

    expect(store.accessToken, 'access-token');
    expect(await store.readRefreshToken(), 'refresh-token');
    expect(
      await secureStorage.read(key: TokenStore.refreshTokenKey),
      'refresh-token',
    );
  });

  test('reads a refresh token persisted before construction', () async {
    FlutterSecureStorage.setMockInitialValues({
      TokenStore.refreshTokenKey: 'persisted-refresh',
    });

    final store = TokenStore();

    expect(store.accessToken, isNull);
    expect(await store.readRefreshToken(), 'persisted-refresh');
  });

  test('clears both access and refresh tokens', () async {
    final store = TokenStore();

    await store.save(
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
    );

    await store.clear();

    expect(store.accessToken, isNull);
    expect(await store.readRefreshToken(), isNull);
  });
}
