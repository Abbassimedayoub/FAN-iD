import 'package:flutter_test/flutter_test.dart';

import '../../../../lib/features/ticketing/domain/fan_ticket.dart';

void main() {
  test('décode un billet retourné par l’API', () {
    final ticket = FanTicket.fromJson(
      <String, dynamic>{
        'id': 'ticket-1',
        'status': 'VALID',
        'event_id': 'event-1',
        'event_name': 'Concert test',
        'event_starts_at': '2026-10-01T20:00:00Z',
        'ticket_category_name': 'Standard',
        'created_at': '2026-09-07T16:00:00Z',
      },
    );

    expect(ticket.id, 'ticket-1');
    expect(ticket.eventName, 'Concert test');
    expect(ticket.statusLabel, 'Valide');
    expect(ticket.isValid, isTrue);
  });

  test('rejette un billet API incomplet', () {
    expect(
      () => FanTicket.fromJson(
        <String, dynamic>{
          'id': 'ticket-1',
        },
      ),
      throwsFormatException,
    );
  });
}
