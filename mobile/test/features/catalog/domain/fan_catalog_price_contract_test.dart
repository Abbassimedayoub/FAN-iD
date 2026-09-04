import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_event.dart';

Map<String, dynamic> eventJson({
  int? minPriceCents,
  int ticketCategoryCount = 0,
  int availableTicketCategoryCount = 0,
  String? imageUrl,
}) {
  return <String, dynamic>{
    'id': 'event-1',
    'category_id': 'category-1',
    'name': 'Derby',
    'description': 'Grand match',
    'venue': 'Stade FANID',
    'capacity_total': 1000,
    'image_url': imageUrl,
    'min_price_cents': minPriceCents,
    'ticket_category_count': ticketCategoryCount,
    'available_ticket_category_count': availableTicketCategoryCount,
    'status': 'PUBLISHED',
    'lifecycle_reason': '',
  };
}

void main() {
  test('affiche le prix exact lorsqu un seul tarif est disponible', () {
    final event = FanCatalogEvent.fromJson(
      eventJson(
        minPriceCents: 1990,
        ticketCategoryCount: 1,
        availableTicketCategoryCount: 1,
      ),
    );

    expect(event.priceLabel, '19,90 €');
  });

  test('affiche a partir du prix minimum avec plusieurs tarifs', () {
    final event = FanCatalogEvent.fromJson(
      eventJson(
        minPriceCents: 1500,
        ticketCategoryCount: 3,
        availableTicketCategoryCount: 2,
      ),
    );

    expect(event.priceLabel, 'À partir de 15 €');
  });

  test('distingue complet et tarif a venir', () {
    final soldOut = FanCatalogEvent.fromJson(
      eventJson(
        ticketCategoryCount: 2,
        availableTicketCategoryCount: 0,
      ),
    );

    final comingSoon = FanCatalogEvent.fromJson(
      eventJson(),
    );

    expect(soldOut.priceLabel, 'Complet');
    expect(comingSoon.priceLabel, 'Tarif à venir');
  });

  test('conserve l url image du contrat API', () {
    final event = FanCatalogEvent.fromJson(
      eventJson(
        imageUrl: 'https://cdn.example.test/event.jpg',
      ),
    );

    expect(
      event.imageUrl,
      'https://cdn.example.test/event.jpg',
    );
  });
}
