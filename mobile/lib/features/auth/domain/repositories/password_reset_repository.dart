abstract interface class PasswordResetRepository {
  Future<int> requestPasswordReset({
    required String email,
  });

  Future<void> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  });
}
