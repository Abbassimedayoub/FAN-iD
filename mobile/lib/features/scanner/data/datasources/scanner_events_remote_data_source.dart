import 'package:dio/dio.dart';

import '../../domain/entities/scanner_assigned_event.dart';

class ScannerEventsRemoteDataSource {
  ScannerEventsRemoteDataSource(this._dio);

  final Dio _dio;

  Future<List<ScannerAssignedEvent>> fetchAssignedEvents() async {
    final response = await _dio.get<dynamic>(
      '/api/v1/scanner/events',
    );

    final body = response.data;

    if (body is List) {
      return _parseItems(body);
    }

    if (body is Map) {
      final map = Map<String, dynamic>.from(body);
      final results = map['results'];

      if (results is List) {
        return _parseItems(results);
      }
    }

    throw const FormatException(
      'Réponse des événements scanner invalide.',
    );
  }

  List<ScannerAssignedEvent> _parseItems(
    List<dynamic> items,
  ) {
    return items
        .whereType<Map>()
        .map(
          (item) => ScannerAssignedEvent.fromJson(
            Map<String, dynamic>.from(item),
          ),
        )
        .toList(growable: false);
  }
}
