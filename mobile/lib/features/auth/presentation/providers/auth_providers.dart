import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/network/dio_client.dart';
import '../../data/datasources/auth_remote_data_source.dart';
import '../../data/repositories/auth_repository_impl.dart';
import '../../data/storage/device_fingerprint_store.dart';
import '../../data/storage/token_store.dart';
import '../../domain/repositories/auth_repository.dart';
import '../../domain/usecases/confirm_device_reset_use_case.dart';
import '../../domain/usecases/login_use_case.dart';
import '../../domain/usecases/register_use_case.dart';
import '../../domain/usecases/request_device_reset_use_case.dart';

final authExpiryGenerationProvider = StateProvider<int>((_) => 0);

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
    onRefreshFailure: () async {
      await tokenStore.clear();
      ref.read(authExpiryGenerationProvider.notifier).state++;
    },
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
    registerUseCase: RegisterUseCase(repository),
    requestDeviceResetUseCase: RequestDeviceResetUseCase(repository),
    confirmDeviceResetUseCase: ConfirmDeviceResetUseCase(repository),
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

final registerUseCaseProvider = Provider<RegisterUseCase>(
  (ref) => ref.watch(authRuntimeProvider).registerUseCase,
);

final requestDeviceResetUseCaseProvider = Provider<RequestDeviceResetUseCase>(
  (ref) => ref.watch(authRuntimeProvider).requestDeviceResetUseCase,
);

final confirmDeviceResetUseCaseProvider = Provider<ConfirmDeviceResetUseCase>(
  (ref) => ref.watch(authRuntimeProvider).confirmDeviceResetUseCase,
);

class AuthRuntime {
  const AuthRuntime({
    required this.tokenStore,
    required this.fingerprintStore,
    required this.dioClient,
    required this.repository,
    required this.loginUseCase,
    required this.registerUseCase,
    required this.requestDeviceResetUseCase,
    required this.confirmDeviceResetUseCase,
  });

  final TokenStore tokenStore;
  final DeviceFingerprintStore fingerprintStore;
  final DioClient dioClient;
  final AuthRepositoryImpl repository;
  final LoginUseCase loginUseCase;
  final RegisterUseCase registerUseCase;
  final RequestDeviceResetUseCase requestDeviceResetUseCase;
  final ConfirmDeviceResetUseCase confirmDeviceResetUseCase;
}
