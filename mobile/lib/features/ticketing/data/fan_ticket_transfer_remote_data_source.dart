import 'package:dio/dio.dart';

import '../../../core/errors/failure.dart';
import '../../../core/network/dio_client.dart';
import '../domain/fan_ticket.dart';

class FanTicketTransferRemoteDataSource {
  const FanTicketTransferRemoteDataSource(this._dio);

  final Dio _dio;

  Future<FanTicket> transferTicket({
    required String ticketId,
    required String recipientEmail,
    required String accessToken,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/v1/tickets/$ticketId/transfer',
        data: <String, String>{
          'recipient_email': recipientEmail.trim(),
        },
        options: Options(
          headers: <String, String>{
            'Authorization': 'Bearer $accessToken',
          },
        ),
      );
      final ticket = response.data?['ticket'];

      if (ticket is! Map) {
        throw const ServerFailure();
      }

      return FanTicket.fromJson(
        Map<String, dynamic>.from(ticket),
      );
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } on FormatException {
      throw const ServerFailure();
    }
  }
}
