import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failure.dart';
import '../../domain/entities/login_session.dart';
import '../../domain/entities/phone_change_challenge.dart';
import '../../domain/entities/scanner_leave_challenge.dart';
import '../providers/auth_providers.dart';

final authControllerProvider =
    AsyncNotifierProvider<AuthController, LoginSession?>(AuthController.new);

class AuthController extends AsyncNotifier<LoginSession?> {
  @override
  Future<LoginSession?> build() async {
    ref.watch(authExpiryGenerationProvider);

    // Une nouvelle instance de l'application constitue une nouvelle session.
    // Le refresh token d'un ancien processus ne doit donc jamais restaurer
    // automatiquement l'utilisateur. Le fingerprint appareil reste persistant.
    await ref.read(tokenStoreProvider).clear();

    return null;
  }

  Future<void> login({
    required String email,
    required String password,
  }) async {
    state = const AsyncLoading();

    state = await AsyncValue.guard(() async {
      final fingerprint =
          await ref.read(deviceFingerprintStoreProvider).getOrCreate();

      return ref.read(loginUseCaseProvider)(
        email: email,
        password: password,
        fingerprint: fingerprint,
        platform: 'android',
      );
    });
  }

  Future<void> updateScannerPhone({
    required String phone,
  }) async {
    await registerFirstPhone(
      phone: phone,
    );
  }

  Future<AuthUser> registerFirstPhone({
    required String phone,
  }) async {
    final currentSession = state.valueOrNull;

    if (currentSession == null) {
      throw const AuthFailure();
    }

    final updatedUser =
        await ref.read(authRuntimeProvider).repository.updatePhone(
              phone: phone,
            );

    _replaceSessionUser(
      currentSession,
      updatedUser,
    );

    return updatedUser;
  }

  Future<PhoneChangeChallenge> requestPhoneChange({
    required String phone,
  }) async {
    final currentSession = state.valueOrNull;

    if (currentSession == null) {
      throw const AuthFailure();
    }

    return ref.read(authRuntimeProvider).repository.requestPhoneChange(
          phone: phone,
        );
  }

  Future<AuthUser> confirmPhoneChange({
    required String challengeId,
    required String phone,
    required String code,
  }) async {
    final currentSession = state.valueOrNull;

    if (currentSession == null) {
      throw const AuthFailure();
    }

    final updatedUser =
        await ref.read(authRuntimeProvider).repository.confirmPhoneChange(
              challengeId: challengeId,
              phone: phone,
              code: code,
            );

    _replaceSessionUser(
      currentSession,
      updatedUser,
    );

    return updatedUser;
  }

  void _replaceSessionUser(
    LoginSession currentSession,
    AuthUser updatedUser,
  ) {
    state = AsyncData(
      LoginSession(
        access: currentSession.access,
        refresh: currentSession.refresh,
        user: updatedUser,
        device: currentSession.device,
      ),
    );
  }

  Future<bool> revalidateScannerSession() async {
    final currentSession = state.valueOrNull;

    if (currentSession == null ||
        currentSession.user.role.toUpperCase() != 'SCANNER') {
      return true;
    }

    final fingerprint =
        await ref.read(deviceFingerprintStoreProvider).getOrCreate();

    try {
      final refreshed = await ref
          .read(authRepositoryProvider)
          .refresh(fingerprint: fingerprint);

      state = AsyncData(refreshed);
      return true;
    } on AuthFailure {
      await ref.read(tokenStoreProvider).clear();
      state = const AsyncData(null);
      return false;
    } on Failure {
      // Une panne réseau temporaire ne doit jamais déconnecter
      // un scanner dont la session est encore valide.
      return true;
    }
  }

  Future<ScannerLeaveChallenge> requestScannerLeaveCode() async {
    final currentSession = state.valueOrNull;

    if (currentSession == null ||
        currentSession.user.role.toUpperCase() != 'SCANNER') {
      throw const AuthFailure();
    }

    return ref.read(authRuntimeProvider).repository.requestScannerLeaveCode();
  }

  Future<void> confirmScannerLeave({
    required String challengeId,
    required String code,
  }) async {
    final currentSession = state.valueOrNull;

    if (currentSession == null ||
        currentSession.user.role.toUpperCase() != 'SCANNER') {
      throw const AuthFailure();
    }

    await ref.read(authRuntimeProvider).repository.confirmScannerLeave(
          challengeId: challengeId,
          code: code,
        );
  }

  Future<void> signOutLocal() async {
    await ref.read(tokenStoreProvider).clear();
    state = const AsyncData(null);
  }
}
