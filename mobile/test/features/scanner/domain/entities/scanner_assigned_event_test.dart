import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/scanner/domain/entities/scanner_assigned_event.dart';

void main() {
  ScannerAssignedEvent event(
    String status,
  ) {
    return ScannerAssignedEvent(
      assignmentId: 'assignment-$status',
      id: 'event-$status',
      name: 'Match',
      startsAt: null,
      endsAt: null,
      venue: '',
      status: status,
      lifecycleReason: '',
    );
  }

  test(
    'mappe les statuts événement pour le scanner',
    () {
      expect(
        event('PUBLISHED').statusLabel,
        'À l’heure',
      );
      expect(
        event('POSTPONED').statusLabel,
        'Retardé / reporté',
      );
      expect(
        event('SUSPENDED').statusLabel,
        'Suspendu',
      );
      expect(
        event('CANCELLED').statusLabel,
        'Annulé',
      );
      expect(
        event('ARCHIVED').statusLabel,
        'Archivé',
      );
    },
  );

  test(
    'marque les statuts interrompus',
    () {
      expect(
        event('PUBLISHED').accessInterrupted,
        isFalse,
      );
      expect(
        event('POSTPONED').accessInterrupted,
        isFalse,
      );
      expect(
        event('SUSPENDED').accessInterrupted,
        isTrue,
      );
      expect(
        event('CANCELLED').accessInterrupted,
        isTrue,
      );
    },
  );

  test(
    'parse la réponse scanner events',
    () {
      final parsed = ScannerAssignedEvent.fromJson(
        <String, dynamic>{
          'assignment_id': 'assignment-1',
          'id': 'event-1',
          'name': 'Finale FANID',
          'starts_at': '2026-09-01T18:00:00Z',
          'ends_at': '2026-09-01T20:00:00Z',
          'postponed_from_starts_at': '2026-08-25T18:00:00Z',
          'postponed_from_ends_at': '2026-08-25T20:00:00Z',
          'postponed_to_starts_at': '2026-09-01T18:00:00Z',
          'postponed_to_ends_at': '2026-09-01T20:00:00Z',
          'venue': 'Paris',
          'status': 'POSTPONED',
          'lifecycle_reason': 'Horaire modifié',
        },
      );

      expect(
        parsed.assignmentId,
        'assignment-1',
      );
      expect(
        parsed.id,
        'event-1',
      );
      expect(
        parsed.name,
        'Finale FANID',
      );
      expect(
        parsed.statusLabel,
        'Retardé / reporté',
      );
      expect(
        parsed.startsAt,
        isNotNull,
      );
      expect(
        parsed.postponedFromStartsAt,
        isNotNull,
      );
      expect(
        parsed.postponedToStartsAt,
        isNotNull,
      );
    },
  );
}
