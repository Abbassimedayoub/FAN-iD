import '../../../../core/errors/failure.dart';
import '../../domain/entities/device_reset_challenge.dart';
import '../../domain/entities/login_session.dart';
import '../../domain/entities/scanner_leave_challenge.dart';
import '../../domain/repositories/auth_repository.dart';
import '../../domain/repositories/password_reset_repository.dart';
import '../datasources/auth_remote_data_source.dart';
import '../storage/token_store.dart';

class AuthRepositoryImpl implements AuthRepository, PasswordResetRepository {
  const AuthRepositoryImpl({
    required this.remoteDataSource,
    required this.tokenStore,
  });

  final AuthRemoteDataSource remoteDataSource;
  final TokenStore tokenStore;

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
    return remoteDataSource.register(
      email: email,
      password: password,
      firstName: firstName,
      lastName: lastName,
      dateOfBirth: dateOfBirth,
      termsAccepted: termsAccepted,
      phone: phone,
    );
  }

  @override
  Future<LoginSession> login({
    required String email,
    required String password,
    String? fingerprint,
    String? platform,
    String label = '',
  }) async {
    final session = await remoteDataSource.login(
      email: email,
      password: password,
      fingerprint: fingerprint,
      platform: platform,
      label: label,
    );

    await tokenStore.save(
      accessToken: session.access,
      refreshToken: session.refresh,
    );

    return session;
  }

  @override
  Future<LoginSession> refresh({String? fingerprint}) async {
    final refreshToken = await tokenStore.readRefreshToken();
    if (refreshToken == null) {
      throw const AuthFailure();
    }

    final session = await remoteDataSource.refresh(
      refreshToken: refreshToken,
      fingerprint: fingerprint,
    );

    await tokenStore.save(
      accessToken: session.access,
      refreshToken: session.refresh,
    );

    return session;
  }

  Future<AuthUser> updatePhone({
    required String phone,
  }) {
    return remoteDataSource.updatePhone(
      phone: phone,
    );
  }

  @override
  Future<void> requestScannerLeave() {
    throw UnsupportedError(
      'Scanner leave requires OTP confirmation.',
    );
  }

  Future<ScannerLeaveChallenge> requestScannerLeaveCode() {
    return remoteDataSource.requestScannerLeaveCode();
  }

  Future<void> confirmScannerLeave({
    required String challengeId,
    required String code,
  }) {
    return remoteDataSource.confirmScannerLeave(
      challengeId: challengeId,
      code: code,
    );
  }

  @override
  Future<DeviceResetChallenge> requestDeviceReset({
    required String email,
    required String password,
  }) {
    return remoteDataSource.requestDeviceReset(
      email: email,
      password: password,
    );
  }

  @override
  Future<void> confirmDeviceReset({
    required String challengeId,
    required String code,
  }) {
    return remoteDataSource.confirmDeviceReset(
      challengeId: challengeId,
      code: code,
    );
  }

  @override
  Future<int> requestPasswordReset({
    required String email,
  }) {
    return remoteDataSource.requestPasswordReset(
      email: email,
    );
  }

  @override
  Future<void> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  }) async {
    await remoteDataSource.confirmPasswordReset(
      email: email,
      code: code,
      newPassword: newPassword,
    );

    // Le backend révoque toutes les sessions après le reset.
    // On supprime également immédiatement les jetons mobiles locaux.
    await tokenStore.clear();
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    await remoteDataSource.changePassword(
      currentPassword: currentPassword,
      newPassword: newPassword,
    );

    // Django révoque les sessions après le changement.
    // On supprime aussi immédiatement les tokens locaux.
    await tokenStore.clear();
  }
}
