import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/cart/data/fan_cart_storage.dart';
import 'package:fanid_mobile/features/cart/domain/fan_cart.dart';
import 'package:fanid_mobile/features/cart/presentation/pages/fan_cart_page.dart';
import 'package:fanid_mobile/features/cart/presentation/providers/fan_cart_provider.dart';

class MemoryFanCartStorage implements FanCartStorage {
  MemoryFanCartStorage(
    Map<String, dynamic> initial,
  ) : value = initial;

  Map<String, dynamic>? value;

  @override
  Future<Map<String, dynamic>?> read() async {
    final current = value;

    if (current == null) {
      return null;
    }

    return Map<String, dynamic>.from(
      current,
    );
  }

  @override
  Future<void> write(
    Map<String, dynamic> value,
  ) async {
    this.value = Map<String, dynamic>.from(
      value,
    );
  }

  @override
  Future<void> clear() async {
    value = null;
  }
}

FanCartItem item({
  required String tariffId,
  required String tariffName,
  int quantity = 2,
}) {
  return FanCartItem(
    eventId: 'event-1',
    eventName: 'REAL MADRID - BARCA',
    ticketCategoryId: tariffId,
    ticketCategoryName: tariffName,
    unitPriceCents: 4000,
    quantity: quantity,
    availableCount: 30,
    eventCapacityTotal: 100,
  );
}

Widget appWithCart(
  FanCart cart,
  DateTime now,
) {
  final storage = MemoryFanCartStorage(
    cart.toJson(),
  );

  return ProviderScope(
    overrides: [
      fanCartControllerProvider.overrideWith(
        (ref, ownerKey) {
          return FanCartController(
            storage: storage,
            now: () => now,
            scheduleExpiryTimers: false,
          );
        },
      ),
    ],
    child: MaterialApp(
      home: Builder(
        builder: (context) {
          return Scaffold(
            body: Center(
              child: FilledButton(
                key: const ValueKey<String>(
                  'open-cart',
                ),
                onPressed: () {
                  Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => const FanCartPage(
                        cartOwnerKey: 'fan@example.com',
                      ),
                    ),
                  );
                },
                child: const Text(
                  'Écran précédent',
                ),
              ),
            ),
          );
        },
      ),
    ),
  );
}

void main() {
  final now = DateTime.utc(
    2026,
    9,
    4,
    20,
  );

  testWidgets(
    'supprimer une ligne entière garde le panier ouvert '
    'si une autre ligne existe',
    (tester) async {
      final cart = FanCart(
        items: <FanCartItem>[
          item(
            tariffId: 'standard',
            tariffName: 'Standard',
            quantity: 3,
          ),
          item(
            tariffId: 'vip',
            tariffName: 'VIP',
          ),
        ],
        expiresAt: now.add(
          const Duration(minutes: 10),
        ),
      );

      await tester.pumpWidget(
        appWithCart(
          cart,
          now,
        ),
      );

      await tester.tap(
        find.byKey(
          const ValueKey<String>(
            'open-cart',
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(
        find.text('Mon panier'),
        findsOneWidget,
      );

      expect(
        find.byKey(
          const ValueKey<String>(
            'fan-cart-item-standard',
          ),
        ),
        findsOneWidget,
      );

      await tester.tap(
        find.byKey(
          const ValueKey<String>(
            'fan-cart-remove-standard',
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(
        find.text('Mon panier'),
        findsOneWidget,
      );

      expect(
        find.byKey(
          const ValueKey<String>(
            'fan-cart-item-standard',
          ),
        ),
        findsNothing,
      );

      expect(
        find.byKey(
          const ValueKey<String>(
            'fan-cart-item-vip',
          ),
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'supprimer la dernière ligne ferme automatiquement '
    'le panier',
    (tester) async {
      final cart = FanCart(
        items: <FanCartItem>[
          item(
            tariffId: 'standard',
            tariffName: 'Standard',
            quantity: 4,
          ),
        ],
        expiresAt: now.add(
          const Duration(minutes: 10),
        ),
      );

      await tester.pumpWidget(
        appWithCart(
          cart,
          now,
        ),
      );

      await tester.tap(
        find.byKey(
          const ValueKey<String>(
            'open-cart',
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(
        find.text('Mon panier'),
        findsOneWidget,
      );

      await tester.tap(
        find.byKey(
          const ValueKey<String>(
            'fan-cart-remove-standard',
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(
        find.text('Mon panier'),
        findsNothing,
      );

      expect(
        find.text('Écran précédent'),
        findsOneWidget,
      );
    },
  );
}
