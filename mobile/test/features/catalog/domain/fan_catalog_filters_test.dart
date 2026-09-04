import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_event.dart';
import 'package:fanid_mobile/features/catalog/domain/fan_catalog_filters.dart';

FanCatalogEvent eventFrom({
  required String id,
  required String status,
  required DateTime? startsAt,
  required DateTime? endsAt,
  String venue = 'Stade A',
  int ticketCategoryCount = 1,
  int availableTicketCategoryCount = 1,
  DateTime? postponedToStartsAt,
  DateTime? postponedToEndsAt,
}) {
  return FanCatalogEvent.fromJson(
    <String, dynamic>{
      'id': id,
      'category_id': 'football',
      'name': id,
      'description': '',
      'starts_at': startsAt?.toIso8601String(),
      'ends_at': endsAt?.toIso8601String(),
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

void main() {
  final now = DateTime.utc(
    2026,
    9,
    4,
    20,
  );

  test(
    'classe correctement à venir, en cours et terminé',
    () {
      final upcoming = eventFrom(
        id: 'upcoming',
        status: 'PUBLISHED',
        startsAt: now.add(
          const Duration(hours: 1),
        ),
        endsAt: now.add(
          const Duration(hours: 3),
        ),
      );

      final ongoing = eventFrom(
        id: 'ongoing',
        status: 'PUBLISHED',
        startsAt: now.subtract(
          const Duration(hours: 1),
        ),
        endsAt: now.add(
          const Duration(hours: 1),
        ),
      );

      final finished = eventFrom(
        id: 'finished',
        status: 'PUBLISHED',
        startsAt: now.subtract(
          const Duration(hours: 3),
        ),
        endsAt: now.subtract(
          const Duration(hours: 1),
        ),
      );

      expect(
        FanCatalogFilters.timeStateAt(
          upcoming,
          now,
        ),
        FanCatalogTimeState.upcoming,
      );

      expect(
        FanCatalogFilters.timeStateAt(
          ongoing,
          now,
        ),
        FanCatalogTimeState.ongoing,
      );

      expect(
        FanCatalogFilters.timeStateAt(
          finished,
          now,
        ),
        FanCatalogTimeState.finished,
      );
    },
  );

  test(
    'un draft reste coming soon et jamais actif',
    () {
      final draft = eventFrom(
        id: 'draft',
        status: 'DRAFT',
        startsAt: now.add(
          const Duration(days: 1),
        ),
        endsAt: now.add(
          const Duration(days: 1, hours: 2),
        ),
        availableTicketCategoryCount: 1,
      );

      expect(draft.isComingSoon, isTrue);

      expect(
        FanCatalogFilters.timeStateAt(
          draft,
          now,
        ),
        FanCatalogTimeState.unknown,
      );

      expect(
        FanCatalogFilters.hasAvailableTickets(
          draft,
        ),
        isFalse,
      );

      expect(
        FanCatalogFilters.isFull(draft),
        isFalse,
      );
    },
  );

  test(
    'un report utilise la nouvelle date si elle existe',
    () {
      final postponed = eventFrom(
        id: 'postponed',
        status: 'POSTPONED',
        startsAt: now.subtract(
          const Duration(days: 10),
        ),
        endsAt: now.subtract(
          const Duration(days: 10, hours: -2),
        ),
        postponedToStartsAt: now.add(
          const Duration(days: 2),
        ),
        postponedToEndsAt: now.add(
          const Duration(days: 2, hours: 2),
        ),
      );

      expect(
        FanCatalogFilters.timeStateAt(
          postponed,
          now,
        ),
        FanCatalogTimeState.upcoming,
      );
    },
  );

  test(
    'un report sans nouvelle date reste hors filtre temporel',
    () {
      final postponed = eventFrom(
        id: 'postponed-unknown',
        status: 'POSTPONED',
        startsAt: now.subtract(
          const Duration(days: 2),
        ),
        endsAt: now.subtract(
          const Duration(days: 2, hours: -2),
        ),
      );

      expect(
        FanCatalogFilters.timeStateAt(
          postponed,
          now,
        ),
        FanCatalogTimeState.unknown,
      );

      expect(
        FanCatalogFilters.hasAvailableTickets(
          postponed,
        ),
        isTrue,
      );
    },
  );

  test(
    'disponible et complet respectent les compteurs',
    () {
      final available = eventFrom(
        id: 'available',
        status: 'PUBLISHED',
        startsAt: now.add(
          const Duration(days: 1),
        ),
        endsAt: now.add(
          const Duration(days: 1, hours: 2),
        ),
        ticketCategoryCount: 2,
        availableTicketCategoryCount: 1,
      );

      final full = eventFrom(
        id: 'full',
        status: 'PUBLISHED',
        startsAt: now.add(
          const Duration(days: 1),
        ),
        endsAt: now.add(
          const Duration(days: 1, hours: 2),
        ),
        ticketCategoryCount: 2,
        availableTicketCategoryCount: 0,
      );

      expect(
        FanCatalogFilters.hasAvailableTickets(
          available,
        ),
        isTrue,
      );
      expect(
        FanCatalogFilters.isFull(available),
        isFalse,
      );

      expect(
        FanCatalogFilters.hasAvailableTickets(
          full,
        ),
        isFalse,
      );
      expect(
        FanCatalogFilters.isFull(full),
        isTrue,
      );
    },
  );

  test(
    'filtre simultanément lieu disponibilité et période',
    () {
      final events = <FanCatalogEvent>[
        eventFrom(
          id: 'wanted',
          status: 'PUBLISHED',
          startsAt: now.add(
            const Duration(hours: 1),
          ),
          endsAt: now.add(
            const Duration(hours: 3),
          ),
          venue: 'Stade B',
        ),
        eventFrom(
          id: 'wrong-venue',
          status: 'PUBLISHED',
          startsAt: now.add(
            const Duration(hours: 1),
          ),
          endsAt: now.add(
            const Duration(hours: 3),
          ),
          venue: 'Stade A',
        ),
        eventFrom(
          id: 'full',
          status: 'PUBLISHED',
          startsAt: now.add(
            const Duration(hours: 1),
          ),
          endsAt: now.add(
            const Duration(hours: 3),
          ),
          venue: 'Stade B',
          availableTicketCategoryCount: 0,
        ),
      ];

      final result = FanCatalogFilters.apply(
        events,
        venue: 'Stade B',
        availability: FanCatalogAvailabilityFilter.available,
        time: FanCatalogTimeFilter.upcoming,
        now: now,
      );

      expect(
        result.map((event) => event.id),
        <String>['wanted'],
      );
    },
  );
}
