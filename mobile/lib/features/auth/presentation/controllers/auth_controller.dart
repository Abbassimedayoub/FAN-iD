import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failure.dart';
import '../../domain/entities/login_session.dart';
import '../providers/auth_providers.dart';

final authControllerProvider =
    AsyncNotifierProvider<AuthController, LoginSession?>(AuthController.new);

class AuthController extends AsyncNotifier<LoginSession?> {
  @override
  Future<LoginSession?> build() async {
    ref.watch(authExpiryGenerationProvider);

    final tokenStore = ref.read(tokenStoreProvider);
    final refreshToken = await tokenStore.readRefreshToken();

    if (refreshToken == null) {
      return null;
    }

    final fingerprint =
        await ref.read(deviceFingerprintStoreProvider).getOrCreate();

    try {
      return await ref
          .read(authRepositoryProvider)
          .refresh(fingerprint: fingerprint);
    } on AuthFailure {
      await tokenStore.clear();
      return null;
    }
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
      );
    });
  }

  Future<void> signOutLocal() async {
    await ref.read(tokenStoreProvider).clear();
    state = const AsyncData(null);
  }
}
