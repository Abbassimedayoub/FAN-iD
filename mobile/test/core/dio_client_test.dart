import 'package:dio/dio.dart';
import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/core/network/dio_client.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
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
        response: Response(requestOptions: RequestOptions(path: '/x'), statusCode: 401),
      );
      expect(mapDioExceptionToFailure(exception), isA<AuthFailure>());
    });

    test('maps a 409 business error to BusinessFailure preserving the code', () {
      final exception = DioException(
        requestOptions: RequestOptions(path: '/x'),
        response: Response(
          requestOptions: RequestOptions(path: '/x'),
          statusCode: 409,
          data: {
            'error': {'code': 'STOCK_UNAVAILABLE', 'message': 'Plus de stock', 'details': {'available': 0}},
          },
        ),
      );
      final failure = mapDioExceptionToFailure(exception);
      expect(failure, isA<BusinessFailure>());
      expect((failure as BusinessFailure).code, 'STOCK_UNAVAILABLE');
      expect(failure.details['available'], 0);
    });

    test('maps a 500 to ServerFailure', () {
      final exception = DioException(
        requestOptions: RequestOptions(path: '/x'),
        response: Response(requestOptions: RequestOptions(path: '/x'), statusCode: 500),
      );
      expect(mapDioExceptionToFailure(exception), isA<ServerFailure>());
    });
  });
}
