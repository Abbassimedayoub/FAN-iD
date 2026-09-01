import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/entities/login_session.dart';
import '../providers/auth_providers.dart';

final registerControllerProvider =
    AsyncNotifierProvider<RegisterController, AuthUser?>(
  RegisterController.new,
);

class RegisterController extends AsyncNotifier<AuthUser?> {
  @override
  Future<AuthUser?> build() async => null;

  Future<void> register({
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    required DateTime dateOfBirth,
    required bool termsAccepted,
    String? phone,
  }) async {
    state = const AsyncLoading();

    state = await AsyncValue.guard(
      () => ref.read(registerUseCaseProvider)(
        email: email,
        password: password,
        firstName: firstName,
        lastName: lastName,
        dateOfBirth: dateOfBirth,
        termsAccepted: termsAccepted,
        phone: phone,
      ),
    );
  }
}
