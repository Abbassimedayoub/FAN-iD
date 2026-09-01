import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/scanner/domain/entities/scanner_assigned_event.dart';
import 'package:fanid_mobile/features/scanner/presentation/pages/scanner_portal_page.dart';

AuthUser scannerUser() {
  return AuthUser(
    id: 'scanner-1',
    email: 'scanner@example.test',
    firstName: 'Samir',
    lastName: 'Scanner',
    role: 'SCANNER',
    createdAt: DateTime.utc(2026, 1, 1),
    phone: '+33612345678',
  );
}

void main() {
  testWidgets(
    'affiche les événements affectés et leurs statuts',
    (tester) async {
      final events = <ScannerAssignedEvent>[
        ScannerAssignedEvent(
          assignmentId: 'assignment-1',
          id: 'event-1',
          name: 'Match Paris',
          startsAt: DateTime.utc(
            2026,
            9,
            1,
            18,
          ),
          endsAt: DateTime.utc(
            2026,
            9,
            1,
            20,
          ),
          venue: 'Stade FANID',
          status: 'PUBLISHED',
          lifecycleReason: '',
        ),
        ScannerAssignedEvent(
          assignmentId: 'assignment-2',
          id: 'event-2',
          name: 'Match Lyon',
          startsAt: DateTime.utc(
            2026,
            9,
            2,
            18,
          ),
          endsAt: DateTime.utc(
            2026,
            9,
            2,
            20,
          ),
          venue: 'Arena FANID',
          status: 'POSTPONED',
          lifecycleReason: 'Horaire modifié',
          postponedFromStartsAt: DateTime.utc(
            2026,
            8,
            20,
            18,
          ),
          postponedFromEndsAt: DateTime.utc(
            2026,
            8,
            20,
            20,
          ),
        ),
        ScannerAssignedEvent(
          assignmentId: 'assignment-3',
          id: 'event-3',
          name: 'Match suspendu',
          startsAt: DateTime.utc(
            2026,
            9,
            3,
            18,
          ),
          endsAt: DateTime.utc(
            2026,
            9,
            3,
            20,
          ),
          venue: 'Centre FANID',
          status: 'SUSPENDED',
          lifecycleReason: 'Incident technique',
        ),
      ];

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: ScannerPortalPage(
              user: scannerUser(),
              loadEvents: () async => events,
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(
        find.text(
          'Mes événements affectés',
        ),
        findsOneWidget,
      );
      expect(
        find.text(
          '3 événements affectés',
        ),
        findsOneWidget,
      );
      expect(
        find.text('Match Paris'),
        findsOneWidget,
      );
      expect(
        find.text('À l’heure'),
        findsOneWidget,
      );
      expect(
        find.text('Match Lyon'),
        findsOneWidget,
      );
      expect(
        find.text(
          'Retardé / reporté',
        ),
        findsOneWidget,
      );

      expect(
        find.textContaining(
          'Nouvelle date à venir',
        ),
        findsOneWidget,
      );
      await tester.scrollUntilVisible(
        find.text('Suspendu'),
        300,
      );

      expect(
        find.text('Suspendu'),
        findsOneWidget,
      );
      expect(
        find.text('Scanner QR'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'affiche un état vide sans affectation',
    (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: ScannerPortalPage(
              user: scannerUser(),
              loadEvents: () async => const <ScannerAssignedEvent>[],
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(
        find.text(
          'Aucun événement affecté',
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'affiche la nouvelle date confirmée au scanner affecté',
    (tester) async {
      final event = ScannerAssignedEvent(
        assignmentId: 'assignment-new-date',
        id: 'event-new-date',
        name: 'Finale reportée',
        startsAt: DateTime.utc(
          2026,
          9,
          20,
          18,
        ),
        endsAt: DateTime.utc(
          2026,
          9,
          20,
          20,
        ),
        postponedFromStartsAt: DateTime.utc(
          2026,
          9,
          10,
          18,
        ),
        postponedFromEndsAt: DateTime.utc(
          2026,
          9,
          10,
          20,
        ),
        postponedToStartsAt: DateTime.utc(
          2026,
          9,
          20,
          18,
        ),
        postponedToEndsAt: DateTime.utc(
          2026,
          9,
          20,
          20,
        ),
        venue: 'Stade FANID',
        status: 'POSTPONED',
        lifecycleReason: 'Nouvelle programmation confirmée',
      );

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: ScannerPortalPage(
              user: scannerUser(),
              loadEvents: () async => <ScannerAssignedEvent>[
                event,
              ],
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(
        find.text('Finale reportée'),
        findsOneWidget,
      );

      expect(
        find.textContaining(
          'Ancienne date :',
        ),
        findsOneWidget,
      );

      expect(
        find.textContaining(
          'Nouvelle date :',
        ),
        findsOneWidget,
      );

      expect(
        find.textContaining(
          '20/09/2026',
        ),
        findsOneWidget,
      );

      expect(
        find.textContaining(
          'Nouvelle date à venir',
        ),
        findsNothing,
      );
    },
  );
}
