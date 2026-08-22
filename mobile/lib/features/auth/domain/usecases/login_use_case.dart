import '../entities/login_session.dart';
import '../repositories/auth_repository.dart';

class LoginUseCase {
  const LoginUseCase(this.repository);

  final AuthRepository repository;

  Future<LoginSession> call({
    required String email,
    required String password,
    String? fingerprint,
    String? platform,
    String label = '',
  }) {
    return repository.login(
      email: email,
      password: password,
      fingerprint: fingerprint,
      platform: platform,
      label: label,
    );
  }
}
