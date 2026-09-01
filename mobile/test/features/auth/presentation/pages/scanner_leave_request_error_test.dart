import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/scanner_leave_request_error.dart';

void main() {
  test(
    'reconnait le conflit métier demande déjà envoyée',
    () {
      const failure = BusinessFailure(
        'SCANNER_LEAVE_ALREADY_REQUESTED',
        'Une demande de départ est déjà en attente.',
      );

      expect(
        isScannerLeaveAlreadyRequested(failure),
        isTrue,
      );
    },
  );

  test(
    'reconnait aussi la réponse Dio brute 409',
    () {
      final request = RequestOptions(
        path: '/api/v1/scanner/leave-request',
      );

      final error = DioException(
        requestOptions: request,
        response: Response<dynamic>(
          requestOptions: request,
          statusCode: 409,
          data: {
            'error': {
              'code': 'SCANNER_LEAVE_ALREADY_REQUESTED',
              'message': 'Une demande de départ est déjà en attente.',
            },
          },
        ),
      );

      expect(
        isScannerLeaveAlreadyRequested(error),
        isTrue,
      );
    },
  );

  test(
    'ne transforme pas une vraie erreur réseau en demande en attente',
    () {
      final error = DioException(
        requestOptions: RequestOptions(
          path: '/api/v1/scanner/leave-request',
        ),
        type: DioExceptionType.connectionError,
      );

      expect(
        isScannerLeaveAlreadyRequested(error),
        isFalse,
      );
    },
  );

  test(
    'ne transforme pas un autre conflit métier',
    () {
      const failure = BusinessFailure(
        'OTHER_BUSINESS_ERROR',
        'Autre erreur',
      );

      expect(
        isScannerLeaveAlreadyRequested(failure),
        isFalse,
      );
    },
  );
}
