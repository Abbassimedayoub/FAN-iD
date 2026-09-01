import '../repositories/password_reset_repository.dart';

class ConfirmPasswordResetUseCase {
  const ConfirmPasswordResetUseCase(this.repository);

  final PasswordResetRepository repository;

  Future<void> call({
    required String email,
    required String code,
    required String newPassword,
  }) {
    return repository.confirmPasswordReset(
      email: email,
      code: code,
      newPassword: newPassword,
    );
  }
}
