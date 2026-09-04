import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/catalog/data/datasources/fan_catalog_remote_data_source.dart';

Map<String, dynamic> eventPayload(
  String? imageUrl,
) {
  return <String, dynamic>{
    'id': 'event-1',
    'category_id': 'football',
    'name': 'REAL MADRID - BARCA',
    'description': 'Clasico',
    'starts_at': '2027-09-04T10:12:00Z',
    'ends_at': '2027-09-04T12:12:00Z',
    'postponed_from_starts_at': null,
    'postponed_from_ends_at': null,
    'postponed_to_starts_at': null,
    'postponed_to_ends_at': null,
    'venue': 'Stade FAN-iD',
    'capacity_total': 1000,
    'image_url': imageUrl,
    'min_price_cents': 4000,
    'ticket_category_count': 2,
    'available_ticket_category_count': 2,
    'status': 'PUBLISHED',
    'published_at': '2026-09-04T19:36:42Z',
    'lifecycle_reason': '',
    'lifecycle_changed_at': null,
  };
}

Dio dioReturningEvent(
  String? imageUrl,
) {
  final dio = Dio(
    BaseOptions(
      baseUrl: 'http://127.0.0.1:8000',
    ),
  );

  dio.interceptors.add(
    InterceptorsWrapper(
      onRequest: (options, handler) {
        handler.resolve(
          Response<Map<String, dynamic>>(
            requestOptions: options,
            statusCode: 200,
            data: <String, dynamic>{
              'count': 1,
              'next': null,
              'previous': null,
              'results': <Map<String, dynamic>>[
                eventPayload(imageUrl),
              ],
            },
          ),
        );
      },
    ),
  );

  return dio;
}

void main() {
  test(
    'resout une image API relative avec la base URL Dio',
    () async {
      final source = FanCatalogRemoteDataSource(
        dioReturningEvent(
          '/api/v1/storage/local/signed-token',
        ),
      );

      final events = await source.fetchEvents(
        'football',
      );

      expect(events, hasLength(1));
      expect(
        events.single.imageUrl,
        'http://127.0.0.1:8000/api/v1/storage/local/signed-token',
      );
    },
  );

  test(
    'conserve une URL image absolue',
    () async {
      final source = FanCatalogRemoteDataSource(
        dioReturningEvent(
          'https://storage.example.test/events/poster.jpg',
        ),
      );

      final events = await source.fetchEvents(
        'football',
      );

      expect(
        events.single.imageUrl,
        'https://storage.example.test/events/poster.jpg',
      );
    },
  );

  test(
    'conserve une image absente a null',
    () async {
      final source = FanCatalogRemoteDataSource(
        dioReturningEvent(null),
      );

      final events = await source.fetchEvents(
        'football',
      );

      expect(
        events.single.imageUrl,
        isNull,
      );
    },
  );
}
