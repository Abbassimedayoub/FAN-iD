import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/cart/domain/fan_cart.dart';

FanCartItem item({
  required String tariffId,
  String eventId = 'event-1',
  String eventName = 'Match',
  String tariffName = 'Standard',
  int price = 2000,
  int quantity = 1,
  int available = 10,
  int? capacity = 20,
}) {
  return FanCartItem(
    eventId: eventId,
    eventName: eventName,
    ticketCategoryId: tariffId,
    ticketCategoryName: tariffName,
    unitPriceCents: price,
    quantity: quantity,
    availableCount: available,
    eventCapacityTotal: capacity,
  );
}

void main() {
  final now = DateTime.utc(
    2026,
    9,
    4,
    20,
  );

  test(
    'ajout, cumul quantité et total',
    () {
      var cart = FanCart.empty();

      cart = cart.addItem(
        item(
          tariffId: 'standard',
          quantity: 2,
          price: 1500,
        ),
        now: now,
      );

      cart = cart.addItem(
        item(
          tariffId: 'vip',
          quantity: 1,
          price: 5000,
        ),
        now: now,
      );

      expect(cart.totalQuantity, 3);
      expect(cart.totalCents, 8000);
      expect(
        cart.expiresAt,
        now.add(
          const Duration(minutes: 10),
        ),
      );
    },
  );

  test(
    'ajouter deux fois le même tarif cumule',
    () {
      var cart = FanCart.empty();

      cart = cart.addItem(
        item(
          tariffId: 'standard',
          quantity: 1,
          available: 3,
        ),
        now: now,
      );

      cart = cart.addItem(
        item(
          tariffId: 'standard',
          quantity: 2,
          available: 3,
        ),
        now: now,
      );

      expect(cart.items, hasLength(1));
      expect(cart.items.single.quantity, 3);
    },
  );

  test(
    'refuse de dépasser la disponibilité tarif',
    () {
      final cart = FanCart.empty();

      expect(
        () => cart.addItem(
          item(
            tariffId: 'standard',
            quantity: 4,
            available: 3,
          ),
          now: now,
        ),
        throwsA(
          isA<FanCartValidationException>(),
        ),
      );
    },
  );

  test(
    'refuse de dépasser la capacité événement',
    () {
      var cart = FanCart.empty();

      cart = cart.addItem(
        item(
          tariffId: 'standard',
          quantity: 2,
          available: 10,
          capacity: 3,
        ),
        now: now,
      );

      expect(
        () => cart.addItem(
          item(
            tariffId: 'vip',
            quantity: 2,
            available: 10,
            capacity: 3,
          ),
          now: now,
        ),
        throwsA(
          isA<FanCartValidationException>(),
        ),
      );
    },
  );

  test(
    'modification ne prolonge pas le TTL initial',
    () {
      var cart = FanCart.empty().addItem(
        item(
          tariffId: 'standard',
        ),
        now: now,
      );

      final initialExpiry = cart.expiresAt;

      final later = now.add(
        const Duration(minutes: 9),
      );

      cart = cart.updateQuantity(
        'standard',
        2,
        now: later,
      );

      expect(
        cart.expiresAt,
        initialExpiry,
      );

      expect(
        cart.expiresAt,
        now.add(
          const Duration(minutes: 10),
        ),
      );

      expect(
        cart.items.single.quantity,
        2,
      );
    },
  );

  test(
    'ajout supplémentaire ne prolonge pas le TTL',
    () {
      var cart = FanCart.empty().addItem(
        item(
          tariffId: 'standard',
        ),
        now: now,
      );

      final initialExpiry = cart.expiresAt;

      cart = cart.addItem(
        item(
          tariffId: 'vip',
          price: 5000,
        ),
        now: now.add(
          const Duration(minutes: 9),
        ),
      );

      expect(cart.items, hasLength(2));
      expect(
        cart.expiresAt,
        initialExpiry,
      );
    },
  );

  test(
    'suppression partielle ne prolonge pas le TTL',
    () {
      var cart = FanCart.empty().addItem(
        item(
          tariffId: 'standard',
        ),
        now: now,
      );

      cart = cart.addItem(
        item(
          tariffId: 'vip',
          price: 5000,
        ),
        now: now,
      );

      final initialExpiry = cart.expiresAt;

      cart = cart.removeItem(
        'vip',
        now: now.add(
          const Duration(minutes: 9),
        ),
      );

      expect(cart.items, hasLength(1));
      expect(
        cart.expiresAt,
        initialExpiry,
      );
    },
  );

  test(
    'suppression du dernier billet vide le panier',
    () {
      final cart = FanCart.empty()
          .addItem(
            item(
              tariffId: 'standard',
            ),
            now: now,
          )
          .removeItem(
            'standard',
            now: now,
          );

      expect(cart.isEmpty, isTrue);
      expect(cart.expiresAt, isNull);
      expect(cart.totalCents, 0);
    },
  );
}
