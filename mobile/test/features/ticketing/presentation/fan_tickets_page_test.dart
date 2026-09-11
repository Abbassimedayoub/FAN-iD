import 'package:fanid_mobile/features/ticketing/domain/fan_ticket.dart';
import 'package:fanid_mobile/features/ticketing/presentation/pages/fan_tickets_page.dart';
import 'package:fanid_mobile/features/ticketing/presentation/providers/fan_tickets_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('renders a valid ticket returned by the tickets provider', (
    tester,
  ) async {
    final startsAt = DateTime.now().toUtc().add(const Duration(days: 365));

    final ticket = FanTicket(
      id: 'ticket-test-1',
      status: 'VALID',
      eventId: 'event-test-1',
      eventName: 'Concert Test FANID',
      eventStartsAt: startsAt,
      eventStatus: 'PUBLISHED',
      postponementReason: null,
      postponedFromStartsAt: null,
      postponedToStartsAt: null,
      ticketCategoryName: 'Catégorie Test',
      issuedAt: DateTime.utc(2026, 9, 1),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          fanTicketsProvider.overrideWith((ref) async => <FanTicket>[ticket]),
        ],
        child: const MaterialApp(home: FanTicketsPage()),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('Concert Test FANID'), findsOneWidget);

    expect(find.text('Catégorie Test'), findsOneWidget);

    expect(tester.takeException(), isNull);
  });
}
