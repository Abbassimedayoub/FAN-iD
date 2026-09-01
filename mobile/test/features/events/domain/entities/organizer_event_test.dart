import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/events/domain/entities/organizer_event.dart';

void main() {
  test(
    'mappe les statuts backend vers les libellés mobiles',
    () {
      OrganizerMobileEvent eventWithStatus(
        String status,
      ) {
        return OrganizerMobileEvent(
          id: status,
          name: 'Match',
          startsAt: null,
          endsAt: null,
          venue: '',
          status: status,
          lifecycleReason: '',
        );
      }

      expect(
        eventWithStatus('PUBLISHED').statusLabel,
        'À l’heure',
      );
      expect(
        eventWithStatus('ON_TIME').statusLabel,
        'À l’heure',
      );
      expect(
        eventWithStatus('POSTPONED').statusLabel,
        'Retardé / reporté',
      );
      expect(
        eventWithStatus('DELAYED').statusLabel,
        'Retardé / reporté',
      );
      expect(
        eventWithStatus('SUSPENDED').statusLabel,
        'Suspendu',
      );
      expect(
        eventWithStatus('CANCELLED').statusLabel,
        'Annulé',
      );
      expect(
        eventWithStatus('ARCHIVED').statusLabel,
        'Archivé',
      );
    },
  );

  test('parse la réponse événement', () {
    final event = OrganizerMobileEvent.fromJson(
      <String, dynamic>{
        'id': 'event-1',
        'name': 'Finale FANID',
        'starts_at': '2026-09-01T18:00:00Z',
        'ends_at': '2026-09-01T20:00:00Z',
        'venue': 'Paris',
        'status': 'SUSPENDED',
        'lifecycle_reason': 'Incident technique',
      },
    );

    expect(event.id, 'event-1');
    expect(event.name, 'Finale FANID');
    expect(event.venue, 'Paris');
    expect(event.statusLabel, 'Suspendu');
    expect(
      event.lifecycleReason,
      'Incident technique',
    );
    expect(event.startsAt, isNotNull);
    expect(event.endsAt, isNotNull);
  });
}
