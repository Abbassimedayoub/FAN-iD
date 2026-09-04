import 'package:dio/dio.dart';

import '../../domain/entities/fan_catalog_category.dart';
import '../../domain/entities/fan_catalog_event.dart';

class FanCatalogRemoteDataSource {
  FanCatalogRemoteDataSource(this._dio);

  final Dio _dio;

  String? _resolveImageUrl(Object? rawValue) {
    final value = rawValue?.toString().trim() ?? '';

    if (value.isEmpty) {
      return null;
    }

    final uri = Uri.tryParse(value);

    if (uri == null || uri.hasScheme) {
      return value;
    }

    final baseUrl = _dio.options.baseUrl.trim();
    final baseUri = Uri.tryParse(baseUrl);

    if (baseUri == null || !baseUri.hasScheme) {
      return value;
    }

    return baseUri.resolve(value).toString();
  }

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
          (item) {
            final json = Map<String, dynamic>.from(item);

            json['image_url'] = _resolveImageUrl(
              json['image_url'],
            );

            return FanCatalogEvent.fromJson(json);
          },
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
