import 'package:dio/dio.dart';
import 'package:fanid_mobile/features/auth/data/datasources/auth_remote_data_source.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('requestPhoneChange sends target phone and parses challenge', () async {
    final dio = Dio(
      BaseOptions(
        baseUrl: 'http://example.test',
      ),
    );

    String? path;
    Object? requestData;

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          path = options.path;
          requestData = options.data;

          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: const {
                'challenge_id': 'challenge-phone',
                'expires_in_seconds': 300,
              },
            ),
          );
        },
      ),
    );

    final dataSource = AuthRemoteDataSource(dio);

    final challenge = await dataSource.requestPhoneChange(
      phone: ' +33699999999 ',
    );

    expect(
      path,
      '/api/v1/auth/phone/change/request',
    );
    expect(
      requestData,
      {
        'phone': '+33699999999',
      },
    );
    expect(
      challenge.challengeId,
      'challenge-phone',
    );
    expect(
      challenge.expiresInSeconds,
      300,
    );
  });

  test('confirmPhoneChange sends OTP and parses updated user', () async {
    final dio = Dio(
      BaseOptions(
        baseUrl: 'http://example.test',
      ),
    );

    String? path;
    Object? requestData;

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          path = options.path;
          requestData = options.data;

          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: const {
                'id': 'user-1',
                'email': 'fan@example.test',
                'first_name': 'Ines',
                'last_name': 'Bouzid',
                'role': 'FAN',
                'created_at': '2026-09-03T20:00:00Z',
                'must_change_password': false,
                'phone': '+33699999999',
              },
            ),
          );
        },
      ),
    );

    final dataSource = AuthRemoteDataSource(dio);

    final user = await dataSource.confirmPhoneChange(
      challengeId: 'challenge-phone',
      phone: ' +33699999999 ',
      code: ' 123456 ',
    );

    expect(
      path,
      '/api/v1/auth/phone/change/confirm',
    );
    expect(
      requestData,
      {
        'challenge_id': 'challenge-phone',
        'phone': '+33699999999',
        'code': '123456',
      },
    );
    expect(
      user.phone,
      '+33699999999',
    );
  });
}
