import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/network/dio_client.dart';
import '../../data/datasources/auth_remote_data_source.dart';
import '../../data/repositories/auth_repository_impl.dart';
import '../../data/storage/device_fingerprint_store.dart';
import '../../data/storage/token_store.dart';
import '../../domain/repositories/auth_repository.dart';
import '../../domain/usecases/login_use_case.dart';

final apiBaseUrlProvider = Provider<String>(
  (_) => const String.fromEnvironment(
    'FANID_API_URL',
    defaultValue: 'http://localhost:8000',
  ),
);

final authRuntimeProvider = Provider<AuthRuntime>((ref) {
  final tokenStore = TokenStore();
  final fingerprintStore = DeviceFingerprintStore();

  late final AuthRepositoryImpl repository;

  final dioClient = DioClient(
    baseUrl: ref.watch(apiBaseUrlProvider),
    tokenProvider: () => tokenStore.accessToken,
    refreshHandler: () async {
      final fingerprint = await fingerprintStore.getOrCreate();
      final session = await repository.refresh(
        fingerprint: fingerprint,
      );
      return session.access;
    },
    onRefreshFailure: tokenStore.clear,
  );

  repository = AuthRepositoryImpl(
    remoteDataSource: AuthRemoteDataSource(dioClient.dio),
    tokenStore: tokenStore,
  );

  return AuthRuntime(
    tokenStore: tokenStore,
    fingerprintStore: fingerprintStore,
    dioClient: dioClient,
    repository: repository,
    loginUseCase: LoginUseCase(repository),
  );
});

final tokenStoreProvider = Provider<TokenStore>(
  (ref) => ref.watch(authRuntimeProvider).tokenStore,
);

final deviceFingerprintStoreProvider = Provider<DeviceFingerprintStore>(
  (ref) => ref.watch(authRuntimeProvider).fingerprintStore,
);

final dioClientProvider = Provider<DioClient>(
  (ref) => ref.watch(authRuntimeProvider).dioClient,
);

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => ref.watch(authRuntimeProvider).repository,
);

final loginUseCaseProvider = Provider<LoginUseCase>(
  (ref) => ref.watch(authRuntimeProvider).loginUseCase,
);

class AuthRuntime {
  const AuthRuntime({
    required this.tokenStore,
    required this.fingerprintStore,
    required this.dioClient,
    required this.repository,
    required this.loginUseCase,
  });

  final TokenStore tokenStore;
  final DeviceFingerprintStore fingerprintStore;
  final DioClient dioClient;
  final AuthRepositoryImpl repository;
  final LoginUseCase loginUseCase;
}
