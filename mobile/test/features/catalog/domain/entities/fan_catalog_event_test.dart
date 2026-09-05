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
  test(
    'parse la phase commerciale calculée par le backend',
    () {
      final event = FanCatalogEvent.fromJson(
        <String, dynamic>{
          'id': 'event-commercial',
          'category_id': 'category-1',
          'name': 'Finale',
          'status': 'PUBLISHED',
          'operational_status': 'COMING_SOON',
          'catalog_status': 'COMING_SOON',
          'sales_open': false,
          'sold_out': false,
          'can_add_to_cart': false,
          'sales_starts_at': '2026-10-01T09:00:00Z',
          'sales_ends_at': '2026-10-10T18:00:00Z',
        },
      );

      expect(event.status, 'PUBLISHED');
      expect(event.operationalStatus, 'COMING_SOON');
      expect(event.catalogStatus, 'COMING_SOON');
      expect(event.effectiveCatalogStatus, 'COMING_SOON');
      expect(event.statusLabel, 'Coming soon');
      expect(
        event.ticketingLabel,
        'Billetterie bientôt disponible',
      );
      expect(event.salesOpen, isFalse);
      expect(event.isSaleOpen, isFalse);
      expect(event.isSoldOut, isFalse);
      expect(event.canAddToCart, isFalse);
      expect(event.salesStartsAt, isNotNull);
      expect(event.salesEndsAt, isNotNull);
    },
  );

  test(
    'mappe toutes les phases catalogue Fan',
    () {
      FanCatalogEvent event(String phase) {
        return FanCatalogEvent.fromJson(
          <String, dynamic>{
            'id': phase,
            'status': 'PUBLISHED',
            'catalog_status': phase,
            'operational_status': phase,
            'sales_open': phase == 'SALE_OPEN',
            'sold_out': phase == 'SOLD_OUT',
            'can_add_to_cart': phase == 'SALE_OPEN',
          },
        );
      }

      expect(
        event('COMING_SOON').statusLabel,
        'Coming soon',
      );
      expect(
        event('SALE_OPEN').statusLabel,
        'Vente ouverte',
      );
      expect(
        event('SOLD_OUT').statusLabel,
        'Complet',
      );
      expect(
        event('SALE_CLOSED').statusLabel,
        'Vente fermée',
      );
      expect(
        event('LIVE').statusLabel,
        'En cours',
      );
      expect(
        event('ENDED').statusLabel,
        'Terminé',
      );

      expect(
        event('SOLD_OUT').ticketingLabel,
        'Complet',
      );
      expect(
        event('SALE_CLOSED').ticketingLabel,
        'Vente terminée',
      );
      expect(
        event('LIVE').ticketingLabel,
        'Événement en cours',
      );
      expect(
        event('ENDED').ticketingLabel,
        'Événement terminé',
      );
    },
  );

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

  test(
    'autorise l achat uniquement pendant SALE_OPEN',
    () {
      FanCatalogEvent makePhase({
        required String catalogStatus,
        required bool salesOpen,
        required bool canAddToCart,
        bool soldOut = false,
        String structuralStatus = 'PUBLISHED',
      }) {
        return FanCatalogEvent.fromJson(
          <String, dynamic>{
            'id': catalogStatus,
            'status': structuralStatus,
            'catalog_status': catalogStatus,
            'operational_status': catalogStatus,
            'sales_open': salesOpen,
            'sold_out': soldOut,
            'can_add_to_cart': canAddToCart,
            'ticket_category_count': 1,
            'available_ticket_category_count': soldOut ? 0 : 1,
          },
        );
      }

      final comingSoon = makePhase(
        catalogStatus: 'COMING_SOON',
        salesOpen: false,
        canAddToCart: true,
      );

      final saleOpen = makePhase(
        catalogStatus: 'SALE_OPEN',
        salesOpen: true,
        canAddToCart: true,
      );

      final soldOut = makePhase(
        catalogStatus: 'SOLD_OUT',
        salesOpen: true,
        canAddToCart: true,
        soldOut: true,
      );

      final saleClosed = makePhase(
        catalogStatus: 'SALE_CLOSED',
        salesOpen: false,
        canAddToCart: true,
      );

      final live = makePhase(
        catalogStatus: 'LIVE',
        salesOpen: false,
        canAddToCart: true,
      );

      final ended = makePhase(
        catalogStatus: 'ENDED',
        salesOpen: false,
        canAddToCart: true,
      );

      final postponed = makePhase(
        catalogStatus: 'POSTPONED',
        salesOpen: false,
        canAddToCart: true,
        structuralStatus: 'POSTPONED',
      );

      expect(
        comingSoon.canPurchaseTickets,
        isFalse,
      );

      expect(
        saleOpen.canPurchaseTickets,
        isTrue,
      );

      expect(
        soldOut.canPurchaseTickets,
        isFalse,
      );

      expect(
        saleClosed.canPurchaseTickets,
        isFalse,
      );

      expect(
        live.canPurchaseTickets,
        isFalse,
      );

      expect(
        ended.canPurchaseTickets,
        isFalse,
      );

      expect(
        postponed.canPurchaseTickets,
        isFalse,
      );
    },
  );

  test(
    'préserve le report lorsque la vente est ouverte',
    () {
      final event = FanCatalogEvent.fromJson(
        <String, dynamic>{
          'id': 'postponed-sale-open',
          'status': 'POSTPONED',
          'operational_status': 'POSTPONED',
          'catalog_status': 'SALE_OPEN',
          'sales_open': true,
          'sold_out': false,
          'can_add_to_cart': true,
          'min_price_cents': 1200,
          'ticket_category_count': 1,
          'available_ticket_category_count': 1,
          'postponed_to_starts_at': '2026-10-10T20:00:00Z',
          'postponed_to_ends_at': '2026-10-10T22:00:00Z',
          'ticket_categories': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'standard',
              'name': 'Standard',
              'unit_price_cents': 1200,
              'available_count': 10,
            },
          ],
        },
      );

      expect(event.statusLabel, 'Reporté');
      expect(event.ticketingLabel, '12 €');
      expect(event.postponedToStartsAt, isNotNull);
      expect(event.canPurchaseTickets, isTrue);
    },
  );
}
