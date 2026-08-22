import 'package:dio/dio.dart';
import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/auth/data/datasources/auth_remote_data_source.dart';
import 'package:fanid_mobile/features/auth/data/repositories/auth_repository_impl.dart';
import 'package:fanid_mobile/features/auth/data/storage/token_store.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeRemoteDataSource extends AuthRemoteDataSource {
  FakeRemoteDataSource(this.result) : super(Dio());

  final LoginSession result;

  @override
  Future<LoginSession> login({
    required String email,
    required String password,
    String? fingerprint,
    String? platform,
    String label = '',
  }) async {
    return result;
  }
}

class FailingRemoteDataSource extends AuthRemoteDataSource {
  FailingRemoteDataSource() : super(Dio());

  @override
  Future<LoginSession> login({
    required String email,
    required String password,
    String? fingerprint,
    String? platform,
    String label = '',
  }) {
    throw const AuthFailure();
  }
}

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  final session = LoginSession(
    access: 'access-token',
    refresh: 'refresh-token',
    user: AuthUser(
      id: 'user-id',
      email: 'fan@example.test',
      firstName: 'Ines',
      lastName: 'Bouzid',
      role: 'FAN',
      createdAt: DateTime.utc(2026),
    ),
    device: null,
  );

  test('stores tokens after a successful remote login', () async {
    final tokenStore = TokenStore();
    final repository = AuthRepositoryImpl(
      remoteDataSource: FakeRemoteDataSource(session),
      tokenStore: tokenStore,
    );

    final result = await repository.login(
      email: 'fan@example.test',
      password: 'secret',
    );

    expect(result, same(session));
    expect(tokenStore.accessToken, 'access-token');
    expect(await tokenStore.readRefreshToken(), 'refresh-token');
  });

  test('does not store tokens when remote login fails', () async {
    final tokenStore = TokenStore();
    final repository = AuthRepositoryImpl(
      remoteDataSource: FailingRemoteDataSource(),
      tokenStore: tokenStore,
    );

    await expectLater(
      repository.login(
        email: 'fan@example.test',
        password: 'wrong',
      ),
      throwsA(isA<AuthFailure>()),
    );

    expect(tokenStore.accessToken, isNull);
    expect(await tokenStore.readRefreshToken(), isNull);
  });
}
