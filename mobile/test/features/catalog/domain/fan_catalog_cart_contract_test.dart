import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_event.dart';

void main() {
  test(
    'parse les tarifs et leur disponibilité',
    () {
      final event = FanCatalogEvent.fromJson(
        <String, dynamic>{
          'id': 'event-1',
          'status': 'PUBLISHED',
          'can_add_to_cart': true,
          'ticket_categories': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'virage',
              'name': 'Virage',
              'unit_price_cents': 4000,
              'available_count': 25,
            },
            <String, dynamic>{
              'id': 'vip',
              'name': 'VIP',
              'unit_price_cents': 5050,
              'available_count': 0,
            },
          ],
        },
      );

      expect(event.canAddToCart, isTrue);
      expect(event.ticketCategories, hasLength(2));

      expect(
        event.ticketCategories.first.name,
        'Virage',
      );
      expect(
        event.ticketCategories.first.priceLabel,
        '40 €',
      );
      expect(
        event.ticketCategories.first.isAvailable,
        isTrue,
      );

      expect(
        event.ticketCategories.last.priceLabel,
        '50,50 €',
      );
      expect(
        event.ticketCategories.last.isAvailable,
        isFalse,
      );
    },
  );

  test(
    'un report sans nouvelle date peut rester achetable',
    () {
      final event = FanCatalogEvent.fromJson(
        <String, dynamic>{
          'id': 'postponed',
          'status': 'POSTPONED',
          'postponed_to_starts_at': null,
          'postponed_to_ends_at': null,
          'can_add_to_cart': true,
          'ticket_categories': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'standard',
              'name': 'Standard',
              'unit_price_cents': 1200,
              'available_count': 22,
            },
          ],
        },
      );

      expect(event.isPostponed, isTrue);
      expect(event.postponedToStartsAt, isNull);
      expect(event.canAddToCart, isTrue);
      expect(
        event.ticketCategories.single.isAvailable,
        isTrue,
      );
    },
  );

  test(
    'valeurs absentes restent rétrocompatibles',
    () {
      final event = FanCatalogEvent.fromJson(
        <String, dynamic>{
          'id': 'legacy',
          'status': 'DRAFT',
        },
      );

      expect(event.canAddToCart, isFalse);
      expect(event.ticketCategories, isEmpty);
    },
  );
}
