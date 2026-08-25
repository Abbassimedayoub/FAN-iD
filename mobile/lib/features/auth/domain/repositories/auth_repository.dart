import '../entities/device_reset_challenge.dart';
import '../entities/login_session.dart';

abstract interface class AuthRepository {
  Future<AuthUser> register({
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    required DateTime dateOfBirth,
    required bool termsAccepted,
    String? phone,
  });

  Future<LoginSession> login({
    required String email,
    required String password,
    String? fingerprint,
    String? platform,
    String label = '',
  });

  Future<LoginSession> refresh({
    String? fingerprint,
  });

  Future<DeviceResetChallenge> requestDeviceReset({
    required String email,
    required String password,
  });

  Future<void> confirmDeviceReset({
    required String challengeId,
    required String code,
  });
}
