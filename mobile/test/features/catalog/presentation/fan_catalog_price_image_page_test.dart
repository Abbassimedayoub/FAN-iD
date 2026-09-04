import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_category.dart';
import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_event.dart';
import 'package:fanid_mobile/features/catalog/presentation/pages/fan_catalog_page.dart';

FanCatalogEvent eventWithoutImage() {
  return const FanCatalogEvent(
    id: 'event-1',
    categoryId: 'category-1',
    name: 'Derby',
    description: 'Grand match',
    startsAt: null,
    endsAt: null,
    postponedFromStartsAt: null,
    postponedFromEndsAt: null,
    postponedToStartsAt: null,
    postponedToEndsAt: null,
    venue: 'Stade FANID',
    capacityTotal: 1000,
    imageUrl: null,
    minPriceCents: 1500,
    ticketCategoryCount: 3,
    availableTicketCategoryCount: 2,
    status: 'PUBLISHED',
    publishedAt: null,
    lifecycleReason: '',
    lifecycleChangedAt: null,
  );
}

void main() {
  testWidgets(
    'affiche fallback image et prix a partir de sur la carte Fan',
    (tester) async {
      const category = FanCatalogCategory(
        id: 'category-1',
        name: 'Football',
        description: '',
      );

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: FanCatalogPage(
              loadCategories: () async {
                return const <FanCatalogCategory>[
                  category,
                ];
              },
              loadEvents: (_) async {
                return <FanCatalogEvent>[
                  eventWithoutImage(),
                ];
              },
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      await tester.tap(
        find.text('Football'),
      );

      await tester.pumpAndSettle();

      expect(
        find.byKey(
          const ValueKey<String>(
            'fan-event-image-fallback-event-1',
          ),
        ),
        findsOneWidget,
      );

      expect(
        find.byKey(
          const ValueKey<String>(
            'fan-event-price-event-1',
          ),
        ),
        findsOneWidget,
      );

      expect(
        find.text('À partir de 15 €'),
        findsOneWidget,
      );
    },
  );
}
