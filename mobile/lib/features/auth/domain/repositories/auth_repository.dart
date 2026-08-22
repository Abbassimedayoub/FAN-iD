import '../entities/login_session.dart';

abstract interface class AuthRepository {
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
}
