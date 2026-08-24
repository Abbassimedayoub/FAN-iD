import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/login_use_case.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeAuthRepository implements AuthRepository {
  String? email;
  String? password;
  String? fingerprint;
  String? platform;
  String? label;

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
    device: AuthDevice(
      id: 'device-id',
      label: 'Pixel 8',
      boundAt: DateTime.utc(2026),
    ),
  );

  @override
  Future<LoginSession> login({
    required String email,
    required String password,
    String? fingerprint,
    String? platform,
    String label = '',
  }) async {
    this.email = email;
    this.password = password;
    this.fingerprint = fingerprint;
    this.platform = platform;
    this.label = label;
    return session;
  }

  @override
  Future<LoginSession> refresh({
    String? fingerprint,
  }) async {
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

void main() {
  test('delegates credentials and device context to the repository', () async {
    final repository = FakeAuthRepository();
    final useCase = LoginUseCase(repository);

    final result = await useCase(
      email: 'fan@example.test',
      password: 'secret',
      fingerprint: 'a' * 64,
      platform: 'android',
      label: 'Pixel 8',
    );

    expect(result, same(repository.session));
    expect(repository.email, 'fan@example.test');
    expect(repository.password, 'secret');
    expect(repository.fingerprint, 'a' * 64);
    expect(repository.platform, 'android');
    expect(repository.label, 'Pixel 8');
  });

  test('allows login without device context', () async {
    final repository = FakeAuthRepository();
    final useCase = LoginUseCase(repository);

    await useCase(
      email: 'fan@example.test',
      password: 'secret',
    );

    expect(repository.fingerprint, isNull);
    expect(repository.platform, isNull);
    expect(repository.label, isEmpty);
  });
}
