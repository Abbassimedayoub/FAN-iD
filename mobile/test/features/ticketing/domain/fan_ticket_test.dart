import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/ticketing/domain/fan_ticket.dart';

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

  test('affiche un billet reporté avec sa nouvelle date', () {
    final ticket = FanTicket.fromJson(
      <String, dynamic>{
        'id': 'ticket-postponed',
        'status': 'VALID',
        'event_id': 'event-1',
        'event_name': 'Concert reporté',
        'event_starts_at': '2026-09-10T18:00:00Z',
        'event_status': 'POSTPONED',
        'postponement_reason': 'Conditions météorologiques.',
        'postponed_from_starts_at': '2026-09-10T18:00:00Z',
        'postponed_to_starts_at': '2026-09-24T18:00:00Z',
        'ticket_category_name': 'VIP',
        'created_at': '2026-09-01T12:00:00Z',
      },
    );

    expect(ticket.isValid, isTrue);
    expect(ticket.isPostponed, isTrue);
    expect(ticket.effectiveStartsAt, DateTime.parse('2026-09-24T18:00:00Z'));
    expect(ticket.postponementReason, 'Conditions météorologiques.');
  });

  test('conserve un billet reporté dont la date est inconnue', () {
    final ticket = FanTicket.fromJson(
      <String, dynamic>{
        'id': 'ticket-date-unknown',
        'status': 'VALID',
        'event_id': 'event-2',
        'event_name': 'Festival reporté',
        'event_starts_at': '2026-09-10T18:00:00Z',
        'event_status': 'POSTPONED',
        'postponement_reason': 'Nouvelle date en préparation.',
        'postponed_from_starts_at': '2026-09-10T18:00:00Z',
        'postponed_to_starts_at': null,
        'ticket_category_name': 'Standard',
        'created_at': '2026-09-01T12:00:00Z',
      },
    );

    expect(ticket.isValid, isTrue);
    expect(ticket.isPostponed, isTrue);
    expect(ticket.postponedToStartsAt, isNull);
    expect(ticket.effectiveStartsAt, DateTime.parse('2026-09-10T18:00:00Z'));
  });
}
