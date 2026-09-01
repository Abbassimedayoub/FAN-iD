import '../repositories/password_reset_repository.dart';

class RequestPasswordResetUseCase {
  const RequestPasswordResetUseCase(this.repository);

  final PasswordResetRepository repository;

  Future<int> call({
    required String email,
  }) {
    return repository.requestPasswordReset(
      email: email,
    );
  }
}
