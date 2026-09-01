import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/auth/data/storage/device_fingerprint_store.dart';
import 'package:fanid_mobile/features/auth/data/storage/token_store.dart';
import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/login_use_case.dart';
import 'package:fanid_mobile/features/auth/presentation/controllers/auth_controller.dart';
import 'package:fanid_mobile/features/auth/presentation/providers/auth_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeAuthRepository implements AuthRepository {
  @override
  Future<void> requestScannerLeave() async {}

  @override
  Future<AuthUser> register({
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    required DateTime dateOfBirth,
    required bool termsAccepted,
    String? phone,
  }) {
    throw UnimplementedError();
  }

  FakeAuthRepository({this.refreshFailure});

  final Failure? refreshFailure;

  String? loginFingerprint;
  String? refreshFingerprint;

  final session = LoginSession(
    access: 'access-token',
    refresh: 'refresh-token',
    user: AuthUser(
      id: 'user-id',
      email: 'fan@example.test',
      firstName: 'Ines',
      lastName: 'Bouzid',
      role: 'FAN',
      createdAt: DateTime.utc(2026),
    ),
    device: null,
  );

  @override
  Future<LoginSession> login({
    required String email,
    required String password,
    String? fingerprint,
    String? platform,
    String label = '',
  }) async {
    loginFingerprint = fingerprint;
    return session;
  }

  @override
  Future<LoginSession> refresh({String? fingerprint}) async {
    refreshFingerprint = fingerprint;
    if (refreshFailure case final failure?) {
      throw failure;
    }
    return session;
  }

  @override
  Future<DeviceResetChallenge> requestDeviceReset({
    required String email,
    required String password,
  }) async {
    return const DeviceResetChallenge(
      challengeId: 'challenge-id',
      expiresInSeconds: 600,
    );
  }

  @override
  Future<void> confirmDeviceReset({
    required String challengeId,
    required String code,
  }) async {}
}

ProviderContainer makeContainer({
  required TokenStore tokenStore,
  required DeviceFingerprintStore fingerprintStore,
  required FakeAuthRepository repository,
}) {
  return ProviderContainer(
    overrides: [
      tokenStoreProvider.overrideWithValue(tokenStore),
      deviceFingerprintStoreProvider.overrideWithValue(fingerprintStore),
      authRepositoryProvider.overrideWithValue(repository),
      loginUseCaseProvider.overrideWithValue(LoginUseCase(repository)),
    ],
  );
}

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  test('bootstrap is signed out when no refresh token exists', () async {
    final repository = FakeAuthRepository();
    final container = makeContainer(
      tokenStore: TokenStore(),
      fingerprintStore: DeviceFingerprintStore(),
      repository: repository,
    );
    addTearDown(container.dispose);

    expect(await container.read(authControllerProvider.future), isNull);
    expect(repository.refreshFingerprint, isNull);
  });

  test('bootstrap refreshes an existing session with fingerprint', () async {
    FlutterSecureStorage.setMockInitialValues({
      TokenStore.refreshTokenKey: 'old-refresh',
      DeviceFingerprintStore.fingerprintKey: 'a' * 64,
    });

    final repository = FakeAuthRepository();
    final container = makeContainer(
      tokenStore: TokenStore(),
      fingerprintStore: DeviceFingerprintStore(),
      repository: repository,
    );
    addTearDown(container.dispose);

    final session = await container.read(authControllerProvider.future);

    expect(session, same(repository.session));
    expect(repository.refreshFingerprint, 'a' * 64);
  });

  test('bootstrap clears local session after AuthFailure', () async {
    FlutterSecureStorage.setMockInitialValues({
      TokenStore.refreshTokenKey: 'old-refresh',
      DeviceFingerprintStore.fingerprintKey: 'a' * 64,
    });

    final tokenStore = TokenStore();
    final container = makeContainer(
      tokenStore: tokenStore,
      fingerprintStore: DeviceFingerprintStore(),
      repository: FakeAuthRepository(refreshFailure: const AuthFailure()),
    );
    addTearDown(container.dispose);

    expect(await container.read(authControllerProvider.future), isNull);
    expect(await tokenStore.readRefreshToken(), isNull);
  });

  test('login supplies the persisted device fingerprint', () async {
    FlutterSecureStorage.setMockInitialValues({
      DeviceFingerprintStore.fingerprintKey: 'b' * 64,
    });

    final repository = FakeAuthRepository();
    final container = makeContainer(
      tokenStore: TokenStore(),
      fingerprintStore: DeviceFingerprintStore(),
      repository: repository,
    );
    addTearDown(container.dispose);

    await container.read(authControllerProvider.future);
    await container.read(authControllerProvider.notifier).login(
          email: 'fan@example.test',
          password: 'secret',
        );

    expect(repository.loginFingerprint, 'b' * 64);
    expect(
        container.read(authControllerProvider).value, same(repository.session));
  });

  test('signOutLocal clears tokens and authentication state', () async {
    final tokenStore = TokenStore();
    await tokenStore.save(
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
    );

    final container = makeContainer(
      tokenStore: tokenStore,
      fingerprintStore: DeviceFingerprintStore(),
      repository: FakeAuthRepository(),
    );
    addTearDown(container.dispose);

    await container.read(authControllerProvider.future);
    await container.read(authControllerProvider.notifier).signOutLocal();

    expect(tokenStore.accessToken, isNull);
    expect(await tokenStore.readRefreshToken(), isNull);
    expect(container.read(authControllerProvider).value, isNull);
  });
}
