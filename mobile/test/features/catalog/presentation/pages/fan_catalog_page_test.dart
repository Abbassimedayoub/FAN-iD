import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_category.dart';
import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_event.dart';
import 'package:fanid_mobile/features/catalog/presentation/pages/fan_catalog_page.dart';

FanCatalogEvent fanEvent({
  required String id,
  required String status,
  String reason = '',
  DateTime? postponedFromStartsAt,
  DateTime? postponedToStartsAt,
}) {
  return FanCatalogEvent(
    id: id,
    categoryId: 'football',
    name: 'Event $id',
    description: '',
    startsAt: DateTime.utc(2026, 10, 1, 18),
    endsAt: DateTime.utc(2026, 10, 1, 20),
    postponedFromStartsAt: postponedFromStartsAt,
    postponedFromEndsAt: null,
    postponedToStartsAt: postponedToStartsAt,
    postponedToEndsAt: null,
    venue: 'Stade FAN-iD',
    capacityTotal: 100,
    imageUrl: null,
    status: status,
    publishedAt: null,
    lifecycleReason: reason,
    lifecycleChangedAt: null,
  );
}

Future<void> openCatalogWithEvents(
  WidgetTester tester,
  List<FanCatalogEvent> events,
) async {
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        home: FanCatalogPage(
          loadCategories: () async => const <FanCatalogCategory>[
            FanCatalogCategory(
              id: 'football',
              name: 'Football',
              description: '',
            ),
          ],
          loadEvents: (_) async => events,
        ),
      ),
    ),
  );

  await tester.pumpAndSettle();

  await tester.tap(find.text('Football'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'DRAFT est affiché Coming soon',
    (tester) async {
      await openCatalogWithEvents(
        tester,
        <FanCatalogEvent>[
          fanEvent(
            id: 'draft',
            status: 'DRAFT',
          ),
        ],
      );

      expect(find.text('Coming soon'), findsOneWidget);
      expect(find.text('Brouillon'), findsNothing);
    },
  );

  testWidgets(
    'PUBLISHED affiche le motif organisateur',
    (tester) async {
      await openCatalogWithEvents(
        tester,
        <FanCatalogEvent>[
          fanEvent(
            id: 'published',
            status: 'PUBLISHED',
            reason: 'Ouverture des portes à 17h',
          ),
        ],
      );

      expect(find.text('Publié'), findsOneWidget);
      expect(
        find.text(
          'Information : Ouverture des portes à 17h',
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'POSTPONED affiche motif et nouvelle date',
    (tester) async {
      await openCatalogWithEvents(
        tester,
        <FanCatalogEvent>[
          fanEvent(
            id: 'postponed-date',
            status: 'POSTPONED',
            reason: 'Conditions météo',
            postponedFromStartsAt: DateTime.utc(2026, 10, 1, 18),
            postponedToStartsAt: DateTime.utc(2026, 10, 20, 18),
          ),
        ],
      );

      expect(find.text('Reporté'), findsOneWidget);
      expect(
        find.text(
          'Motif du report : Conditions météo',
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining(
          'Nouvelle date : 20/10/2026',
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining('Date initiale :'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'POSTPONED indique si nouvelle date inconnue',
    (tester) async {
      await openCatalogWithEvents(
        tester,
        <FanCatalogEvent>[
          fanEvent(
            id: 'postponed-no-date',
            status: 'POSTPONED',
            reason: 'Conditions météo',
            postponedFromStartsAt: DateTime.utc(2026, 10, 1, 18),
          ),
        ],
      );

      expect(find.text('Reporté'), findsOneWidget);
      expect(
        find.text(
          'Motif du report : Conditions météo',
        ),
        findsOneWidget,
      );
      expect(
        find.text(
          'Nouvelle date : pas encore renseignée par '
          'l’organisateur.',
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'SUSPENDED affiche motif et nouvelle date renseignée',
    (tester) async {
      await openCatalogWithEvents(
        tester,
        <FanCatalogEvent>[
          fanEvent(
            id: 'suspended-date',
            status: 'SUSPENDED',
            reason: 'Incident technique',
            postponedToStartsAt: DateTime.utc(2026, 10, 15, 18),
          ),
        ],
      );

      expect(find.text('Suspendu'), findsOneWidget);
      expect(
        find.text(
          'Motif de suspension : Incident technique',
        ),
        findsOneWidget,
      );
      expect(
        find.textContaining(
          'Nouvelle date : 15/10/2026',
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'SUSPENDED indique si nouvelle date non renseignée',
    (tester) async {
      await openCatalogWithEvents(
        tester,
        <FanCatalogEvent>[
          fanEvent(
            id: 'suspended-no-date',
            status: 'SUSPENDED',
            reason: 'Décision organisateur',
          ),
        ],
      );

      expect(find.text('Suspendu'), findsOneWidget);
      expect(
        find.text(
          'Motif de suspension : Décision organisateur',
        ),
        findsOneWidget,
      );
      expect(
        find.text(
          'Nouvelle date : pas encore renseignée par '
          'l’organisateur.',
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'CANCELLED affiche le motif annulation',
    (tester) async {
      await openCatalogWithEvents(
        tester,
        <FanCatalogEvent>[
          fanEvent(
            id: 'cancelled',
            status: 'CANCELLED',
            reason: 'Annulation par organisateur',
          ),
        ],
      );

      expect(find.text('Annulé'), findsOneWidget);
      expect(
        find.text(
          'Motif d’annulation : Annulation par organisateur',
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'ARCHIVED est totalement invisible pour le Fan',
    (tester) async {
      await openCatalogWithEvents(
        tester,
        <FanCatalogEvent>[
          fanEvent(
            id: 'archived',
            status: 'ARCHIVED',
            reason: 'Archive interne',
          ),
        ],
      );

      expect(
        find.text(
          'Aucun événement dans cette catégorie.',
        ),
        findsOneWidget,
      );
      expect(find.text('Event archived'), findsNothing);
      expect(find.text('Archivé'), findsNothing);
      expect(
        find.textContaining('Archive interne'),
        findsNothing,
      );
    },
  );
}
