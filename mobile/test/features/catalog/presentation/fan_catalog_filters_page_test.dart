import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_category.dart';
import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_event.dart';
import 'package:fanid_mobile/features/catalog/presentation/pages/fan_catalog_page.dart';

FanCatalogEvent makeEvent({
  required String id,
  required String name,
  required String status,
  required DateTime startsAt,
  required DateTime endsAt,
  required String venue,
  int ticketCategoryCount = 1,
  int availableTicketCategoryCount = 1,
  DateTime? postponedToStartsAt,
  DateTime? postponedToEndsAt,
}) {
  return FanCatalogEvent.fromJson(
    <String, dynamic>{
      'id': id,
      'category_id': 'football',
      'name': name,
      'description': '',
      'starts_at': startsAt.toIso8601String(),
      'ends_at': endsAt.toIso8601String(),
      'postponed_from_starts_at': null,
      'postponed_from_ends_at': null,
      'postponed_to_starts_at': postponedToStartsAt?.toIso8601String(),
      'postponed_to_ends_at': postponedToEndsAt?.toIso8601String(),
      'venue': venue,
      'capacity_total': 100,
      'image_url': null,
      'min_price_cents': ticketCategoryCount > 0 ? 1200 : null,
      'ticket_category_count': ticketCategoryCount,
      'available_ticket_category_count': availableTicketCategoryCount,
      'status': status,
      'published_at': null,
      'lifecycle_reason': '',
      'lifecycle_changed_at': null,
    },
  );
}

Future<void> pumpCatalog(
  WidgetTester tester, {
  required List<FanCatalogEvent> events,
  required DateTime now,
}) async {
  final category = FanCatalogCategory.fromJson(
    <String, dynamic>{
      'id': 'football',
      'name': 'Football',
      'description': 'Matchs',
    },
  );

  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        home: FanCatalogPage(
          loadCategories: () async => <FanCatalogCategory>[
            category,
          ],
          loadEvents: (_) async => events,
          now: () => now,
        ),
      ),
    ),
  );

  await tester.pumpAndSettle();

  await tester.tap(
    find.byKey(
      const ValueKey<String>(
        'fan-category-football',
      ),
    ),
  );

  await tester.pumpAndSettle();
}

Future<void> tapFilter(
  WidgetTester tester,
  String key,
) async {
  final finder = find.byKey(
    ValueKey<String>(key),
  );

  expect(finder, findsOneWidget);

  final widget = tester.widget<Widget>(finder);

  if (widget is ChoiceChip) {
    final callback = widget.onSelected;

    expect(callback, isNotNull);

    callback!(true);
  } else if (widget is TextButton) {
    final callback = widget.onPressed;

    expect(callback, isNotNull);

    callback!();
  } else {
    fail(
      'Widget de filtre inattendu pour $key: '
      '${widget.runtimeType}',
    );
  }

  await tester.pumpAndSettle();
}

void main() {
  final now = DateTime.utc(
    2026,
    9,
    4,
    20,
  );

  testWidgets(
    'affiche les filtres lieu disponibilité et période',
    (tester) async {
      final events = <FanCatalogEvent>[
        makeEvent(
          id: 'future-a',
          name: 'Future A',
          status: 'PUBLISHED',
          startsAt: now.add(
            const Duration(hours: 2),
          ),
          endsAt: now.add(
            const Duration(hours: 4),
          ),
          venue: 'Stade A',
        ),
        makeEvent(
          id: 'ongoing-full',
          name: 'Ongoing Full',
          status: 'PUBLISHED',
          startsAt: now.subtract(
            const Duration(hours: 1),
          ),
          endsAt: now.add(
            const Duration(hours: 1),
          ),
          venue: 'Stade A',
          availableTicketCategoryCount: 0,
        ),
        makeEvent(
          id: 'finished-b',
          name: 'Finished B',
          status: 'PUBLISHED',
          startsAt: now.subtract(
            const Duration(hours: 4),
          ),
          endsAt: now.subtract(
            const Duration(hours: 2),
          ),
          venue: 'Stade B',
        ),
        makeEvent(
          id: 'draft-b',
          name: 'Draft B',
          status: 'DRAFT',
          startsAt: now.add(
            const Duration(days: 1),
          ),
          endsAt: now.add(
            const Duration(days: 1, hours: 2),
          ),
          venue: 'Stade B',
        ),
        makeEvent(
          id: 'postponed-unknown',
          name: 'Postponed Unknown',
          status: 'POSTPONED',
          startsAt: now.subtract(
            const Duration(days: 1),
          ),
          endsAt: now.subtract(
            const Duration(hours: 22),
          ),
          venue: 'Stade C',
        ),
        makeEvent(
          id: 'postponed-future',
          name: 'Postponed Future',
          status: 'POSTPONED',
          startsAt: now.subtract(
            const Duration(days: 2),
          ),
          endsAt: now.subtract(
            const Duration(hours: 46),
          ),
          venue: 'Stade C',
          postponedToStartsAt: now.add(
            const Duration(days: 2),
          ),
          postponedToEndsAt: now.add(
            const Duration(days: 2, hours: 2),
          ),
        ),
      ];

      await pumpCatalog(
        tester,
        events: events,
        now: now,
      );

      expect(
        find.byKey(
          const ValueKey<String>(
            'fan-catalog-filters',
          ),
        ),
        findsOneWidget,
      );

      expect(
        find.text('6 / 6 événements'),
        findsOneWidget,
      );

      await tapFilter(
        tester,
        'fan-filter-venue-Stade B',
      );

      expect(
        find.text('2 / 6 événements'),
        findsOneWidget,
      );

      await tapFilter(
        tester,
        'fan-filter-reset',
      );

      expect(
        find.text('6 / 6 événements'),
        findsOneWidget,
      );

      await tapFilter(
        tester,
        'fan-filter-availability-full',
      );

      expect(
        find.text('1 / 6 événements'),
        findsOneWidget,
      );

      await tapFilter(
        tester,
        'fan-filter-reset',
      );

      await tapFilter(
        tester,
        'fan-filter-time-upcoming',
      );

      expect(
        find.text('2 / 6 événements'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'un brouillon est présenté comme coming soon non actif',
    (tester) async {
      final draft = makeEvent(
        id: 'draft',
        name: 'Nouveau match',
        status: 'DRAFT',
        startsAt: now.add(
          const Duration(days: 1),
        ),
        endsAt: now.add(
          const Duration(days: 1, hours: 2),
        ),
        venue: 'Stade A',
      );

      await pumpCatalog(
        tester,
        events: <FanCatalogEvent>[draft],
        now: now,
      );

      expect(
        find.text('Coming soon'),
        findsOneWidget,
      );

      expect(
        find.text(
          'Billetterie bientôt disponible',
        ),
        findsOneWidget,
      );

      expect(
        find.text('12 €'),
        findsNothing,
      );
    },
  );
}
