import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/cart/presentation/widgets/fan_ticket_selection_sheet.dart';
import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_event.dart';
import 'package:fanid_mobile/features/catalog/domain/entities/fan_catalog_ticket_category.dart';

FanCatalogEvent makeEvent() {
  return FanCatalogEvent.fromJson(
    <String, dynamic>{
      'id': 'event-1',
      'category_id': 'football',
      'name': 'REAL MADRID - BARCA',
      'description': '',
      'starts_at': '2027-09-04T10:12:00Z',
      'ends_at': '2027-09-04T12:12:00Z',
      'venue': 'STADE DE FRANCE',
      'capacity_total': 50,
      'image_url': null,
      'min_price_cents': 4000,
      'ticket_category_count': 2,
      'available_ticket_category_count': 1,
      'can_add_to_cart': true,
      'ticket_categories': <Map<String, dynamic>>[
        <String, dynamic>{
          'id': 'virage',
          'name': 'Virage',
          'unit_price_cents': 4000,
          'available_count': 2,
        },
        <String, dynamic>{
          'id': 'vip',
          'name': 'VIP',
          'unit_price_cents': 5000,
          'available_count': 0,
        },
      ],
      'status': 'PUBLISHED',
      'published_at': null,
      'lifecycle_reason': '',
      'lifecycle_changed_at': null,
    },
  );
}

void main() {
  testWidgets(
    'sélectionne tarif, quantité et ajoute',
    (tester) async {
      FanCatalogTicketCategory? selected;
      int? selectedQuantity;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: FanTicketSelectionSheet(
              event: makeEvent(),
              onAdd: (
                tariff,
                quantity,
              ) async {
                selected = tariff;
                selectedQuantity = quantity;
              },
            ),
          ),
        ),
      );

      expect(
        find.textContaining('Virage'),
        findsWidgets,
      );

      expect(
        find.byKey(
          const ValueKey<String>(
            'fan-ticket-quantity',
          ),
        ),
        findsOneWidget,
      );

      await tester.tap(
        find.byKey(
          const ValueKey<String>(
            'fan-ticket-increment',
          ),
        ),
      );

      await tester.pump();

      expect(
        find.text('2'),
        findsOneWidget,
      );

      final increment = tester.widget<IconButton>(
        find.byKey(
          const ValueKey<String>(
            'fan-ticket-increment',
          ),
        ),
      );

      expect(
        increment.onPressed,
        isNull,
      );

      await tester.tap(
        find.byKey(
          const ValueKey<String>(
            'fan-ticket-add',
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(selected?.id, 'virage');
      expect(selectedQuantity, 2);
    },
  );
}
