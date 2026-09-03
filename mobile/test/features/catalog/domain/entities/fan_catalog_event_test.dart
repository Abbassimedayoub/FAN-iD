import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_event.dart';

FanCatalogEvent eventWithStatus(String status) {
  return FanCatalogEvent(
    id: status,
    categoryId: 'category-1',
    name: 'Match',
    description: '',
    startsAt: null,
    endsAt: null,
    postponedFromStartsAt: null,
    postponedFromEndsAt: null,
    postponedToStartsAt: null,
    postponedToEndsAt: null,
    venue: '',
    capacityTotal: null,
    imageUrl: null,
    status: status,
    publishedAt: null,
    lifecycleReason: '',
    lifecycleChangedAt: null,
  );
}

void main() {
  test('mappe les statuts visibles destinés au Fan', () {
    expect(
      eventWithStatus('DRAFT').statusLabel,
      'Coming soon',
    );
    expect(
      eventWithStatus('PUBLISHED').statusLabel,
      'Publié',
    );
    expect(
      eventWithStatus('POSTPONED').statusLabel,
      'Reporté',
    );
    expect(
      eventWithStatus('SUSPENDED').statusLabel,
      'Suspendu',
    );
    expect(
      eventWithStatus('CANCELLED').statusLabel,
      'Annulé',
    );
  });

  test('parse les détails et motifs renvoyés par le backend', () {
    final event = FanCatalogEvent.fromJson(
      <String, dynamic>{
        'id': 'event-1',
        'category_id': 'category-1',
        'name': 'Finale FAN-iD',
        'description': 'Grande finale',
        'starts_at': '2026-10-01T18:00:00Z',
        'ends_at': '2026-10-01T20:00:00Z',
        'postponed_from_starts_at': '2026-09-30T18:00:00Z',
        'postponed_from_ends_at': '2026-09-30T20:00:00Z',
        'postponed_to_starts_at': '2026-10-15T18:00:00Z',
        'postponed_to_ends_at': '2026-10-15T20:00:00Z',
        'venue': 'Stade FAN-iD',
        'capacity_total': 5000,
        'image_url': '/api/v1/storage/local/token',
        'status': 'SUSPENDED',
        'published_at': '2026-09-01T12:00:00Z',
        'lifecycle_reason': 'Incident technique',
        'lifecycle_changed_at': '2026-09-02T10:00:00Z',
      },
    );

    expect(event.id, 'event-1');
    expect(event.categoryId, 'category-1');
    expect(event.statusLabel, 'Suspendu');
    expect(event.capacityTotal, 5000);
    expect(
      event.lifecycleReason,
      'Incident technique',
    );
    expect(event.postponedToStartsAt, isNotNull);
  });
}
