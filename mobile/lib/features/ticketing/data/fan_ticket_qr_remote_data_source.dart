import 'package:dio/dio.dart';

import '../../../core/errors/failure.dart';
import '../../../core/network/dio_client.dart';
import '../domain/fan_ticket.dart';

class FanTicketQrRemoteDataSource {
  const FanTicketQrRemoteDataSource(this._dio);

  final Dio _dio;

  Future<FanTicketQr> fetchQr({
    required String ticketId,
    required String accessToken,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/tickets/$ticketId/qr',
        options: Options(
          headers: <String, String>{
            'Authorization': 'Bearer $accessToken',
          },
        ),
      );

      final data = response.data;
      if (data == null) {
        throw const ServerFailure();
      }

      return FanTicketQr.fromJson(data);
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } on FormatException {
      throw const ServerFailure();
    }
  }
}
