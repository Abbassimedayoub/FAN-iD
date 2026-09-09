import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/ticketing/domain/fan_ticket.dart';
import 'package:fanid_mobile/features/ticketing/domain/fan_ticket_filters.dart';

FanTicket ticket({
  required String id,
  required String status,
  required String startsAt,
}) {
  return FanTicket.fromJson(
    <String, dynamic>{
      'id': id,
      'status': status,
      'event_id': 'event-$id',
      'event_name': 'Événement $id',
      'event_starts_at': startsAt,
      'ticket_category_name': 'Standard',
      'created_at': '2026-01-01T10:00:00Z',
    },
  );
}

void main() {
  final now = DateTime.utc(2026, 9, 9, 12);

  test('trie les billets à venir par événement le plus proche', () {
    final result = filterAndSortFanTickets(
      <FanTicket>[
        ticket(id: 'far', status: 'VALID', startsAt: '2026-10-10T18:00:00Z'),
        ticket(id: 'near', status: 'VALID', startsAt: '2026-09-10T18:00:00Z'),
      ],
      dateFilter: FanTicketDateFilter.upcoming,
      statusFilter: FanTicketStatusFilter.all,
      now: now,
    );

    expect(result.map((item) => item.id), <String>['near', 'far']);
  });

  test('filtre les billets passés et utilisés', () {
    final result = filterAndSortFanTickets(
      <FanTicket>[
        ticket(id: 'used', status: 'USED', startsAt: '2026-09-01T18:00:00Z'),
        ticket(id: 'valid', status: 'VALID', startsAt: '2026-09-02T18:00:00Z'),
        ticket(id: 'future', status: 'USED', startsAt: '2026-10-02T18:00:00Z'),
      ],
      dateFilter: FanTicketDateFilter.past,
      statusFilter: FanTicketStatusFilter.used,
      now: now,
    );

    expect(result.single.id, 'used');
  });
}
