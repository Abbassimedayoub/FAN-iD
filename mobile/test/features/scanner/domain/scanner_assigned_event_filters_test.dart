import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/scanner/domain/entities/scanner_assigned_event.dart';
import 'package:fanid_mobile/features/scanner/domain/scanner_assigned_event_filters.dart';

ScannerAssignedEvent event({
  required String id,
  required String status,
  required DateTime startsAt,
}) {
  return ScannerAssignedEvent(
    assignmentId: 'assignment-$id',
    id: id,
    name: 'Événement $id',
    startsAt: startsAt,
    endsAt: startsAt.add(const Duration(hours: 2)),
    venue: 'FANID',
    status: status,
    lifecycleReason: '',
  );
}

void main() {
  final now = DateTime.utc(2026, 9, 9, 12);

  test('trie les événements Scanner à venir par proximité', () {
    final result = filterAndSortScannerEvents(
      <ScannerAssignedEvent>[
        event(
          id: 'far',
          status: 'PUBLISHED',
          startsAt: DateTime.utc(2026, 10, 10, 18),
        ),
        event(
          id: 'near',
          status: 'POSTPONED',
          startsAt: DateTime.utc(2026, 9, 10, 18),
        ),
      ],
      dateFilter: ScannerEventDateFilter.upcoming,
      statusFilter: ScannerEventStatusFilter.all,
      now: now,
    );

    expect(result.map((item) => item.id), <String>['near', 'far']);
  });

  test('filtre les événements Scanner suspendus', () {
    final result = filterAndSortScannerEvents(
      <ScannerAssignedEvent>[
        event(
          id: 'suspended',
          status: 'SUSPENDED',
          startsAt: DateTime.utc(2026, 9, 10, 18),
        ),
        event(
          id: 'published',
          status: 'PUBLISHED',
          startsAt: DateTime.utc(2026, 9, 11, 18),
        ),
      ],
      dateFilter: ScannerEventDateFilter.all,
      statusFilter: ScannerEventStatusFilter.suspended,
      now: now,
    );

    expect(result.single.id, 'suspended');
  });
}
