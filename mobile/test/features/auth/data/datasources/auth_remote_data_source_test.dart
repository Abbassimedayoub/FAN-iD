import 'package:dio/dio.dart';
import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/auth/data/datasources/auth_remote_data_source.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
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

  test('maps an HTTP login error to Failure', () async {
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

    final source = AuthRemoteDataSource(dio);

    expect(
      () => source.login(
        email: 'fan@example.test',
        password: 'wrong',
      ),
      throwsA(isA<AuthFailure>()),
    );
  });
}
