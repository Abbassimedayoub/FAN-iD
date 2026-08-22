import 'dart:async';

import 'package:dio/dio.dart';
import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/core/network/dio_client.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('DioClient refresh lock', () {
    test('shares one in-flight refresh between concurrent callers', () async {
      final completer = Completer<String>();
      var calls = 0;

      final client = DioClient(
        baseUrl: 'https://example.test',
        tokenProvider: () => null,
        refreshHandler: () {
          calls += 1;
          return completer.future;
        },
      );

      final first = client.refreshAccessTokenOnce();
      final second = client.refreshAccessTokenOnce();

      expect(calls, 1);

      completer.complete('new-access');

      expect(await first, 'new-access');
      expect(await second, 'new-access');
      expect(calls, 1);
    });

    test('releases the refresh lock after a failure', () async {
      var calls = 0;

      final client = DioClient(
        baseUrl: 'https://example.test',
        tokenProvider: () => null,
        refreshHandler: () async {
          calls += 1;
          if (calls == 1) {
            throw StateError('refresh failed');
          }
          return 'new-access';
        },
      );

      await expectLater(
        client.refreshAccessTokenOnce(),
        throwsA(isA<StateError>()),
      );

      expect(await client.refreshAccessTokenOnce(), 'new-access');
      expect(calls, 2);
    });
  });

  group('mapDioExceptionToFailure', () {
    test('maps a connectionError (no response) to NetworkFailure', () {
      final exception = DioException(
        requestOptions: RequestOptions(path: '/x'),
        type: DioExceptionType.connectionError,
      );
      expect(mapDioExceptionToFailure(exception), isA<NetworkFailure>());
    });

    test('maps a 401 to AuthFailure', () {
      final exception = DioException(
        requestOptions: RequestOptions(path: '/x'),
        response: Response(
            requestOptions: RequestOptions(path: '/x'), statusCode: 401),
      );
      expect(mapDioExceptionToFailure(exception), isA<AuthFailure>());
    });

    test('maps a 409 business error to BusinessFailure preserving the code',
        () {
      final exception = DioException(
        requestOptions: RequestOptions(path: '/x'),
        response: Response(
          requestOptions: RequestOptions(path: '/x'),
          statusCode: 409,
          data: {
            'error': {
              'code': 'STOCK_UNAVAILABLE',
              'message': 'Plus de stock',
              'details': {'available': 0}
            },
          },
        ),
      );
      final failure = mapDioExceptionToFailure(exception);
      expect(failure, isA<BusinessFailure>());
      expect((failure as BusinessFailure).code, 'STOCK_UNAVAILABLE');
      expect(failure.details['available'], 0);
    });

    test('maps DEVICE_LOCKED 403 to BusinessFailure preserving details', () {
      final exception = DioException(
        requestOptions: RequestOptions(path: '/x'),
        response: Response(
          requestOptions: RequestOptions(path: '/x'),
          statusCode: 403,
          data: {
            'error': {
              'code': 'DEVICE_LOCKED',
              'message': 'Un autre appareil est déjà lié',
              'details': {
                'reset_available': true,
                'active_device_label': 'Pixel 8',
              },
            },
          },
        ),
      );

      final failure = mapDioExceptionToFailure(exception);

      expect(failure, isA<BusinessFailure>());
      final business = failure as BusinessFailure;
      expect(business.code, 'DEVICE_LOCKED');
      expect(business.details['reset_available'], isTrue);
      expect(business.details['active_device_label'], 'Pixel 8');
    });

    test('maps a generic 403 to PermissionFailure', () {
      final exception = DioException(
        requestOptions: RequestOptions(path: '/x'),
        response: Response(
          requestOptions: RequestOptions(path: '/x'),
          statusCode: 403,
        ),
      );

      expect(mapDioExceptionToFailure(exception), isA<PermissionFailure>());
    });

    test('maps a 500 to ServerFailure', () {
      final exception = DioException(
        requestOptions: RequestOptions(path: '/x'),
        response: Response(
            requestOptions: RequestOptions(path: '/x'), statusCode: 500),
      );
      expect(mapDioExceptionToFailure(exception), isA<ServerFailure>());
    });
  });
}
