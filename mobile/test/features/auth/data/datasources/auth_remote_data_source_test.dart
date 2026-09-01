import 'package:dio/dio.dart';
import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/auth/data/datasources/auth_remote_data_source.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('posts the registration contract and parses the public user', () async {
    late RequestOptions captured;
    final dio = Dio();

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          captured = options;
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 201,
              data: {
                'id': 'user-id',
                'email': 'fan@example.test',
                'first_name': 'Ines',
                'last_name': 'Bouzid',
                'role': 'FAN',
                'created_at': '2026-08-24T20:00:00Z',
              },
            ),
          );
        },
      ),
    );

    final user = await AuthRemoteDataSource(dio).register(
      email: 'fan@example.test',
      password: 'Strong-Password-2026',
      firstName: 'Ines',
      lastName: 'Bouzid',
      dateOfBirth: DateTime.utc(1996, 5, 4),
      termsAccepted: true,
      phone: '+33600000000',
    );

    expect(captured.path, '/api/v1/auth/register');
    expect(captured.method, 'POST');
    expect(captured.data, {
      'email': 'fan@example.test',
      'password': 'Strong-Password-2026',
      'first_name': 'Ines',
      'last_name': 'Bouzid',
      'date_of_birth': '1996-05-04',
      'terms_accepted': true,
      'phone': '+33600000000',
    });
    expect(user.id, 'user-id');
    expect(user.role, 'FAN');
  });

  test('registration omits phone when absent', () async {
    late RequestOptions captured;
    final dio = Dio();

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          captured = options;
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 201,
              data: {
                'id': 'user-id',
                'email': 'fan@example.test',
                'first_name': 'Ines',
                'last_name': 'Bouzid',
                'role': 'FAN',
                'created_at': '2026-08-24T20:00:00Z',
              },
            ),
          );
        },
      ),
    );

    await AuthRemoteDataSource(dio).register(
      email: 'fan@example.test',
      password: 'Strong-Password-2026',
      firstName: 'Ines',
      lastName: 'Bouzid',
      dateOfBirth: DateTime.utc(1996, 5, 4),
      termsAccepted: true,
    );

    expect((captured.data as Map).containsKey('phone'), isFalse);
  });

  test('registration preserves business errors', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.reject(
            DioException(
              requestOptions: options,
              response: Response(
                requestOptions: options,
                statusCode: 400,
                data: {
                  'error': {
                    'code': 'EMAIL_ALREADY_EXISTS',
                    'message': 'Un compte existe déjà pour cette adresse.',
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
      AuthRemoteDataSource(dio).register(
        email: 'fan@example.test',
        password: 'Strong-Password-2026',
        firstName: 'Ines',
        lastName: 'Bouzid',
        dateOfBirth: DateTime.utc(1996, 5, 4),
        termsAccepted: true,
      ),
      throwsA(
        isA<BusinessFailure>().having(
          (failure) => failure.code,
          'code',
          'EMAIL_ALREADY_EXISTS',
        ),
      ),
    );
  });

  test('registration rejects empty or malformed responses', () async {
    for (final data in <Map<String, dynamic>?>[
      null,
      {'id': 42},
    ]) {
      final dio = Dio();
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (options, handler) {
            handler.resolve(
              Response<Map<String, dynamic>>(
                requestOptions: options,
                statusCode: 201,
                data: data,
              ),
            );
          },
        ),
      );

      await expectLater(
        AuthRemoteDataSource(dio).register(
          email: 'fan@example.test',
          password: 'Strong-Password-2026',
          firstName: 'Ines',
          lastName: 'Bouzid',
          dateOfBirth: DateTime.utc(1996, 5, 4),
          termsAccepted: true,
        ),
        throwsA(isA<ServerFailure>()),
      );
    }
  });

  test('posts the mobile login contract and parses the response', () async {
    late RequestOptions captured;

    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          captured = options;
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: {
                'access': 'access-token',
                'refresh': 'refresh-token',
                'user': {
                  'id': 'user-id',
                  'email': 'fan@example.test',
                  'first_name': 'Ines',
                  'last_name': 'Bouzid',
                  'role': 'FAN',
                  'created_at': '2026-08-22T12:00:00Z',
                },
                'device': {
                  'id': 'device-id',
                  'label': 'Pixel 8',
                  'bound_at': '2026-08-22T12:00:00Z',
                },
              },
            ),
          );
        },
      ),
    );

    final source = AuthRemoteDataSource(dio);

    final session = await source.login(
      email: 'fan@example.test',
      password: 'secret',
      fingerprint: 'a' * 64,
      platform: 'android',
      label: 'Pixel 8',
    );

    expect(captured.path, '/api/v1/auth/login');
    expect(captured.method, 'POST');
    expect(captured.data, {
      'email': 'fan@example.test',
      'password': 'secret',
      'client': 'mobile',
      'fingerprint': 'a' * 64,
      'platform': 'android',
      'label': 'Pixel 8',
    });

    expect(session.access, 'access-token');
    expect(session.refresh, 'refresh-token');
    expect(session.user.role, 'FAN');
    expect(session.device?.label, 'Pixel 8');
  });

  test('accepts a login response without a device', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: {
                'access': 'access-token',
                'refresh': 'refresh-token',
                'user': {
                  'id': 'user-id',
                  'email': 'fan@example.test',
                  'first_name': '',
                  'last_name': '',
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

    final session = await AuthRemoteDataSource(dio).login(
      email: 'fan@example.test',
      password: 'secret',
    );

    expect(session.device, isNull);
  });

  test('posts mobile refresh and parses the rotated tokens', () async {
    late RequestOptions captured;

    final dio = Dio();
    dio.interceptors.add(
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

    final session = await AuthRemoteDataSource(dio).refresh(
      refreshToken: 'old-refresh',
      fingerprint: 'a' * 64,
    );

    expect(captured.path, '/api/v1/auth/token/refresh');
    expect(captured.data, {
      'client': 'mobile',
      'refresh': 'old-refresh',
      'fingerprint': 'a' * 64,
    });
    expect(session.access, 'new-access');
    expect(session.refresh, 'new-refresh');
  });

  test('preserves ServerFailure when login or refresh has no body', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: null,
            ),
          );
        },
      ),
    );

    final source = AuthRemoteDataSource(dio);

    await expectLater(
      source.login(email: 'fan@example.test', password: 'secret'),
      throwsA(isA<ServerFailure>()),
    );

    await expectLater(
      source.refresh(refreshToken: 'refresh-token'),
      throwsA(isA<ServerFailure>()),
    );
  });

  test('maps an HTTP refresh error to Failure', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.reject(
            DioException(
              requestOptions: options,
              response: Response(
                requestOptions: options,
                statusCode: 401,
              ),
            ),
          );
        },
      ),
    );

    await expectLater(
      AuthRemoteDataSource(dio).refresh(refreshToken: 'refresh-token'),
      throwsA(isA<AuthFailure>()),
    );
  });

  test('preserves INVALID_CREDENTIALS on login', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.reject(
            DioException(
              requestOptions: options,
              response: Response(
                requestOptions: options,
                statusCode: 401,
                data: {
                  'error': {
                    'code': 'INVALID_CREDENTIALS',
                    'message': 'Adresse ou mot de passe incorrect.',
                    'details': <String, dynamic>{},
                  },
                },
              ),
            ),
          );
        },
      ),
    );

    final source = AuthRemoteDataSource(dio);

    await expectLater(
      source.login(
        email: 'fan@example.test',
        password: 'wrong',
      ),
      throwsA(
        isA<BusinessFailure>()
            .having((failure) => failure.code, 'code', 'INVALID_CREDENTIALS'),
      ),
    );
  });

  test('keeps generic login 401 mapped to AuthFailure', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.reject(
            DioException(
              requestOptions: options,
              response: Response(
                requestOptions: options,
                statusCode: 401,
              ),
            ),
          );
        },
      ),
    );

    await expectLater(
      AuthRemoteDataSource(dio).login(
        email: 'fan@example.test',
        password: 'wrong',
      ),
      throwsA(isA<AuthFailure>()),
    );
  });

  test('requests and parses a device reset challenge', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          expect(options.path, '/api/v1/devices/reset/request');
          expect(options.data, {
            'email': 'fan@example.test',
            'password': 'secret',
          });

          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: {
                'challenge_id': 'challenge-id',
                'expires_in_seconds': 600,
              },
            ),
          );
        },
      ),
    );

    final result = await AuthRemoteDataSource(dio).requestDeviceReset(
      email: 'fan@example.test',
      password: 'secret',
    );

    expect(result.challengeId, 'challenge-id');
    expect(result.expiresInSeconds, 600);
  });

  test('device reset request rejects an empty response', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: null,
            ),
          );
        },
      ),
    );

    await expectLater(
      AuthRemoteDataSource(dio).requestDeviceReset(
        email: 'fan@example.test',
        password: 'secret',
      ),
      throwsA(isA<ServerFailure>()),
    );
  });

  test('device reset request maps HTTP errors', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.reject(
            DioException(
              requestOptions: options,
              response: Response(
                requestOptions: options,
                statusCode: 500,
              ),
            ),
          );
        },
      ),
    );

    await expectLater(
      AuthRemoteDataSource(dio).requestDeviceReset(
        email: 'fan@example.test',
        password: 'secret',
      ),
      throwsA(isA<ServerFailure>()),
    );
  });

  test('device reset request rejects a malformed response', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: {
                'challenge_id': 'challenge-id',
                'expires_in_seconds': 'invalid',
              },
            ),
          );
        },
      ),
    );

    await expectLater(
      AuthRemoteDataSource(dio).requestDeviceReset(
        email: 'fan@example.test',
        password: 'secret',
      ),
      throwsA(isA<ServerFailure>()),
    );
  });

  test('confirms a device reset challenge', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          expect(options.path, '/api/v1/devices/reset/confirm');
          expect(options.data, {
            'challenge_id': 'challenge-id',
            'code': '123456',
          });

          handler.resolve(
            Response<void>(
              requestOptions: options,
              statusCode: 204,
            ),
          );
        },
      ),
    );

    await AuthRemoteDataSource(dio).confirmDeviceReset(
      challengeId: 'challenge-id',
      code: '123456',
    );
  });

  test('device reset confirm preserves OTP_INVALID', () async {
    final dio = Dio();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          handler.reject(
            DioException(
              requestOptions: options,
              response: Response(
                requestOptions: options,
                statusCode: 400,
                data: {
                  'error': {
                    'code': 'OTP_INVALID',
                    'message': 'Code incorrect.',
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
      AuthRemoteDataSource(dio).confirmDeviceReset(
        challengeId: 'challenge-id',
        code: 'wrong',
      ),
      throwsA(
        isA<BusinessFailure>()
            .having((failure) => failure.code, 'code', 'OTP_INVALID'),
      ),
    );
  });
}
