import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/confirm_device_reset_use_case.dart';
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

  String? challengeId;
  String? code;

  @override
  Future<void> confirmDeviceReset({
    required String challengeId,
    required String code,
  }) async {
    this.challengeId = challengeId;
    this.code = code;
  }

  @override
  Future<DeviceResetChallenge> requestDeviceReset({
    required String email,
    required String password,
  }) =>
      throw UnimplementedError();

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
}

void main() {
  test('delegates challenge and code to repository', () async {
    final repository = FakeAuthRepository();
    final useCase = ConfirmDeviceResetUseCase(repository);

    await useCase(
      challengeId: 'challenge-id',
      code: '123456',
    );

    expect(repository.challengeId, 'challenge-id');
    expect(repository.code, '123456');
  });
}
