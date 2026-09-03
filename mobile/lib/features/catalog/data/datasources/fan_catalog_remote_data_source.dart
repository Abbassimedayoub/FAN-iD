import 'package:dio/dio.dart';

import '../../domain/entities/fan_catalog_category.dart';
import '../../domain/entities/fan_catalog_event.dart';

class FanCatalogRemoteDataSource {
  FanCatalogRemoteDataSource(this._dio);

  final Dio _dio;

  Future<List<FanCatalogCategory>> fetchCategories() async {
    final response = await _dio.get<dynamic>(
      '/api/v1/catalog/categories',
    );

    final body = response.data;

    if (body is! List) {
      throw const FormatException(
        'Réponse catégories Catalogue Fan invalide.',
      );
    }

    return body
        .whereType<Map>()
        .map(
          (item) => FanCatalogCategory.fromJson(
            Map<String, dynamic>.from(item),
          ),
        )
        .toList(growable: false);
  }

  Future<List<FanCatalogEvent>> fetchEvents(
    String categoryId,
  ) async {
    final events = <FanCatalogEvent>[];
    final visitedPages = <String>{};

    String? nextPage = '/api/v1/catalog/events?category_id=$categoryId';

    while (nextPage != null && visitedPages.add(nextPage)) {
      final response = await _dio.get<dynamic>(nextPage);
      final body = response.data;

      if (body is! Map) {
        throw const FormatException(
          'Réponse événements Catalogue Fan invalide.',
        );
      }

      final data = Map<String, dynamic>.from(body);
      final results = data['results'];

      if (results is! List) {
        throw const FormatException(
          'Liste événements Catalogue Fan invalide.',
        );
      }

      events.addAll(
        results.whereType<Map>().map(
              (item) => FanCatalogEvent.fromJson(
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
