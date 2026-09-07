import 'package:dio/dio.dart';

import '../../../../core/errors/failure.dart';
import '../../../../core/network/dio_client.dart';

class ScannerAdmissionResult {
  const ScannerAdmissionResult({
    required this.admissionId,
    required this.ticketId,
  });

  final String admissionId;
  final String ticketId;
}

class TicketAdmissionRemoteDataSource {
  const TicketAdmissionRemoteDataSource(this._dio);

  final Dio _dio;

  Future<ScannerAdmissionResult> admit(String token) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/access/scans',
        data: <String, dynamic>{'token': token},
      );

      final data = response.data;
      final admissionId = data?['admission_id']?.toString();
      final ticketId = data?['ticket_id']?.toString();

      if (data?['status'] != 'ADMITTED' ||
          admissionId == null ||
          admissionId.isEmpty ||
          ticketId == null ||
          ticketId.isEmpty) {
        throw const ServerFailure();
      }

      return ScannerAdmissionResult(
        admissionId: admissionId,
        ticketId: ticketId,
      );
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } catch (_) {
      throw const ServerFailure();
    }
  }
}
