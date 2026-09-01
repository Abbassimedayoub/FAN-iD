import 'package:dio/dio.dart';

import '../../domain/entities/organizer_event.dart';

class OrganizerEventsRemoteDataSource {
  OrganizerEventsRemoteDataSource(this._dio);

  final Dio _dio;

  Future<List<OrganizerMobileEvent>> fetchAll() async {
    final events = <OrganizerMobileEvent>[];
    final visitedPages = <String>{};

    String? nextPage = '/api/v1/events';

    while (nextPage != null && visitedPages.add(nextPage)) {
      final response = await _dio.get<dynamic>(nextPage);
      final body = response.data;

      if (body is List) {
        events.addAll(
          body.whereType<Map>().map(
                (item) => OrganizerMobileEvent.fromJson(
                  Map<String, dynamic>.from(item),
                ),
              ),
        );
        break;
      }

      if (body is! Map) {
        throw const FormatException(
          'Réponse événements organisateur invalide.',
        );
      }

      final data = Map<String, dynamic>.from(body);
      final results = data['results'];

      if (results is! List) {
        throw const FormatException(
          'Liste événements organisateur invalide.',
        );
      }

      events.addAll(
        results.whereType<Map>().map(
              (item) => OrganizerMobileEvent.fromJson(
                Map<String, dynamic>.from(item),
              ),
            ),
      );

      final rawNext = data['next'];
      nextPage = rawNext == null || rawNext.toString().trim().isEmpty
          ? null
          : rawNext.toString();
    }

    return events;
  }
}
