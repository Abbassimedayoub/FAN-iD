import 'package:dio/dio.dart';

import '../../../core/network/dio_client.dart';

import '../../../../core/errors/failure.dart';
import '../domain/fan_ticket.dart';

class FanTicketsRemoteDataSource {
  const FanTicketsRemoteDataSource(this._dio);

  final Dio _dio;

  Future<List<FanTicket>> fetchTickets() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/tickets',
      );

      final results = response.data?['results'];

      if (results is! List) {
        throw const ServerFailure();
      }

      return results
          .map(
            (item) => FanTicket.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(growable: false);
    } on DioException catch (error) {
      throw mapDioExceptionToFailure(error);
    } on Failure {
      rethrow;
    } on FormatException {
      throw const ServerFailure();
    }
  }
}
