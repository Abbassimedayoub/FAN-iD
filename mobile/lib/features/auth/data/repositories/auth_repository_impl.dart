import '../../domain/entities/login_session.dart';
import '../../domain/repositories/auth_repository.dart';
import '../datasources/auth_remote_data_source.dart';
import '../storage/token_store.dart';

class AuthRepositoryImpl implements AuthRepository {
  const AuthRepositoryImpl({
    required this.remoteDataSource,
    required this.tokenStore,
  });

  final AuthRemoteDataSource remoteDataSource;
  final TokenStore tokenStore;

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
}
