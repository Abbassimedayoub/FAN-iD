import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:dio/dio.dart';
import 'package:fanid_mobile/features/auth/data/storage/device_fingerprint_store.dart';
import 'package:fanid_mobile/features/auth/data/storage/token_store.dart';
import 'package:fanid_mobile/features/auth/presentation/providers/auth_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  test('uses the default API base URL', () {
    final container = ProviderContainer();
    addTearDown(container.dispose);

    expect(container.read(apiBaseUrlProvider), 'http://10.0.2.2:8000');
  });

  test('wires the auth runtime through Riverpod', () async {
    final container = ProviderContainer(
      overrides: [
        apiBaseUrlProvider.overrideWithValue('https://api.example.test'),
      ],
    );
    addTearDown(container.dispose);

    final runtime = container.read(authRuntimeProvider);

    await runtime.tokenStore.save(
      accessToken: 'old-access',
      refreshToken: 'old-refresh',
    );

    expect(runtime.dioClient.dio.options.baseUrl, 'https://api.example.test');
    expect(runtime.dioClient.tokenProvider(), 'old-access');
    expect(container.read(tokenStoreProvider), same(runtime.tokenStore));
    expect(
      container.read(deviceFingerprintStoreProvider),
      same(runtime.fingerprintStore),
    );
    expect(container.read(dioClientProvider), same(runtime.dioClient));
    expect(container.read(authRepositoryProvider), same(runtime.repository));
    expect(container.read(loginUseCaseProvider), same(runtime.loginUseCase));
    expect(
      container.read(registerUseCaseProvider),
      same(runtime.registerUseCase),
    );
    expect(
      container.read(requestDeviceResetUseCaseProvider),
      same(runtime.requestDeviceResetUseCase),
    );
    expect(
      container.read(confirmDeviceResetUseCaseProvider),
      same(runtime.confirmDeviceResetUseCase),
    );
  });

  test('refresh handler uses persisted fingerprint and refresh token',
      () async {
    FlutterSecureStorage.setMockInitialValues({
      TokenStore.refreshTokenKey: 'old-refresh',
      DeviceFingerprintStore.fingerprintKey: 'a' * 64,
    });

    final container = ProviderContainer(
      overrides: [
        apiBaseUrlProvider.overrideWithValue('https://api.example.test'),
      ],
    );
    addTearDown(container.dispose);

    final runtime = container.read(authRuntimeProvider);
    late RequestOptions captured;

    runtime.dioClient.dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          captured = options;
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: {
                'access': 'new-access',
                'refresh': 'new-refresh',
                'user': {
                  'id': 'user-id',
                  'email': 'fan@example.test',
                  'first_name': 'Ines',
                  'last_name': 'Bouzid',
                  'role': 'FAN',
                  'created_at': '2026-08-22T12:00:00Z',
                },
                'device': null,
              },
            ),
          );
        },
      ),
    );

    expect(await runtime.dioClient.refreshAccessTokenOnce(), 'new-access');
    expect(captured.path, '/api/v1/auth/token/refresh');
    expect(captured.data, {
      'client': 'mobile',
      'refresh': 'old-refresh',
      'fingerprint': 'a' * 64,
    });
    expect(runtime.tokenStore.accessToken, 'new-access');
  });

  test(
    'refresh network failure preserves tokens and does not signal session expiry',
    () async {
      final container = ProviderContainer(
        overrides: [
          apiBaseUrlProvider.overrideWithValue('https://api.example.test'),
        ],
      );
      addTearDown(container.dispose);

      final runtime = container.read(authRuntimeProvider);

      await runtime.tokenStore.save(
        accessToken: 'old-access',
        refreshToken: 'old-refresh',
      );

      runtime.dioClient.dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (options, handler) {
            handler.reject(
              DioException(
                requestOptions: options,
                type: DioExceptionType.connectionError,
                error: 'offline',
              ),
            );
          },
        ),
      );

      await expectLater(
        runtime.dioClient.refreshAccessTokenOnce(),
        throwsA(anything),
      );

      expect(runtime.tokenStore.accessToken, 'old-access');
      expect(await runtime.tokenStore.readRefreshToken(), 'old-refresh');
      expect(container.read(authExpiryGenerationProvider), 0);
    },
  );

  test('invalid refresh clears tokens and signals session expiry', () async {
    final container = ProviderContainer(
      overrides: [
        apiBaseUrlProvider.overrideWithValue('https://api.example.test'),
      ],
    );
    addTearDown(container.dispose);

    final runtime = container.read(authRuntimeProvider);

    await runtime.tokenStore.save(
      accessToken: 'old-access',
      refreshToken: 'old-refresh',
    );

    runtime.dioClient.dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.reject(
            DioException(
              requestOptions: options,
              type: DioExceptionType.badResponse,
              response: Response<dynamic>(
                requestOptions: options,
                statusCode: 401,
                data: const {
                  'error': {
                    'code': 'TOKEN_INVALID',
                    'message': 'Session invalide',
                    'details': <String, dynamic>{},
                  },
                },
              ),
            ),
          );
        },
      ),
    );

    await expectLater(
      runtime.dioClient.refreshAccessTokenOnce(),
      throwsA(isA<AuthFailure>()),
    );

    expect(runtime.tokenStore.accessToken, isNull);
    expect(await runtime.tokenStore.readRefreshToken(), isNull);
    expect(container.read(authExpiryGenerationProvider), 1);
  });
}
