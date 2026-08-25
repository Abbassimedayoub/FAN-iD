import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/request_device_reset_use_case.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeAuthRepository implements AuthRepository {
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

  String? email;
  String? password;

  @override
  Future<DeviceResetChallenge> requestDeviceReset({
    required String email,
    required String password,
  }) async {
    this.email = email;
    this.password = password;
    return const DeviceResetChallenge(
      challengeId: 'challenge-id',
      expiresInSeconds: 600,
    );
  }

  @override
  Future<LoginSession> login({
    required String email,
    required String password,
    String? fingerprint,
    String? platform,
    String label = '',
  }) =>
      throw UnimplementedError();

  @override
  Future<LoginSession> refresh({String? fingerprint}) =>
      throw UnimplementedError();

  @override
  Future<void> confirmDeviceReset({
    required String challengeId,
    required String code,
  }) async {}
}

void main() {
  test('delegates credentials to repository', () async {
    final repository = FakeAuthRepository();
    final useCase = RequestDeviceResetUseCase(repository);

    final result = await useCase(
      email: 'fan@example.test',
      password: 'secret',
    );

    expect(result.challengeId, 'challenge-id');
    expect(result.expiresInSeconds, 600);
    expect(repository.email, 'fan@example.test');
    expect(repository.password, 'secret');
  });
}
