import 'package:dio/dio.dart';

import '../../../../core/errors/failure.dart';

const scannerLeaveAlreadyRequestedCode = 'SCANNER_LEAVE_ALREADY_REQUESTED';

bool isScannerLeaveAlreadyRequested(Object error) {
  if (error is BusinessFailure) {
    return error.code == scannerLeaveAlreadyRequestedCode;
  }

  if (error is DioException) {
    final body = error.response?.data;

    if (body is Map && body['error'] is Map) {
      final apiError = body['error'] as Map;

      return apiError['code'] == scannerLeaveAlreadyRequestedCode;
    }
  }

  return false;
}
