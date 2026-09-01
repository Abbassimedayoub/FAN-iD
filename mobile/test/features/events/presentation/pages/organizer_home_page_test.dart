import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/events/domain/entities/organizer_event.dart';
import 'package:fanid_mobile/features/events/presentation/pages/organizer_home_page.dart';

AuthUser organizerUser() => AuthUser(
      id: 'organizer-1',
      email: 'organizer@example.test',
      firstName: 'Amina',
      lastName: 'FANID',
      role: 'ORGANIZER',
      createdAt: DateTime.utc(2026, 1, 1),
    );

void main() {
  testWidgets(
    'affiche les événements organisateur avec leurs statuts',
    (tester) async {
      final events = <OrganizerMobileEvent>[
        OrganizerMobileEvent(
          id: 'on-time',
          name: 'Match à l’heure',
          startsAt: DateTime.utc(2026, 9, 1, 18),
          endsAt: DateTime.utc(2026, 9, 1, 20),
          venue: 'Stade FANID',
          status: 'PUBLISHED',
          lifecycleReason: '',
        ),
        OrganizerMobileEvent(
          id: 'delayed',
          name: 'Match retardé',
          startsAt: DateTime.utc(2026, 9, 2, 18),
          endsAt: DateTime.utc(2026, 9, 2, 20),
          venue: 'Arena FANID',
          status: 'POSTPONED',
          lifecycleReason: 'Horaire modifié',
        ),
        OrganizerMobileEvent(
          id: 'suspended',
          name: 'Match suspendu',
          startsAt: DateTime.utc(2026, 9, 3, 18),
          endsAt: DateTime.utc(2026, 9, 3, 20),
          venue: 'Centre FANID',
          status: 'SUSPENDED',
          lifecycleReason: 'Incident',
        ),
      ];

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: OrganizerHomePage(
              user: organizerUser(),
              loadEvents: () async => events,
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Mes événements'), findsOneWidget);
      expect(find.text('3 événements'), findsOneWidget);
      expect(find.text('Match à l’heure'), findsOneWidget);
      expect(find.text('À l’heure'), findsOneWidget);
      expect(find.text('Match retardé'), findsOneWidget);
      expect(find.text('Retardé / reporté'), findsOneWidget);
      expect(find.text('Match suspendu'), findsOneWidget);
      expect(find.text('Suspendu'), findsOneWidget);
      expect(find.text('Information : Incident'), findsOneWidget);
    },
  );

  testWidgets(
    'affiche un état vide quand aucun événement existe',
    (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: OrganizerHomePage(
              user: organizerUser(),
              loadEvents: () async => const <OrganizerMobileEvent>[],
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Aucun événement'), findsOneWidget);
    },
  );
}
