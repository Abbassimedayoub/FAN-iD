import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/cart/data/fan_cart_storage.dart';
import 'package:fanid_mobile/features/cart/domain/fan_cart.dart';
import 'package:fanid_mobile/features/cart/presentation/providers/fan_cart_provider.dart';

FanCart cartValue(
  AsyncValue<FanCart> state,
) {
  return state.when(
    data: (cart) => cart,
    loading: () => throw StateError(
      'Panier encore en chargement.',
    ),
    error: (error, _) => throw StateError(
      'Panier en erreur: $error',
    ),
  );
}

class MemoryFanCartStorage implements FanCartStorage {
  Map<String, dynamic>? value;

  int clearCount = 0;
  int writeCount = 0;

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
    writeCount++;

    this.value = Map<String, dynamic>.from(value);
  }

  @override
  Future<void> clear() async {
    clearCount++;
    value = null;
  }
}

FanCartItem makeItem() {
  return const FanCartItem(
    eventId: 'event-1',
    eventName: 'Match',
    ticketCategoryId: 'tariff-1',
    ticketCategoryName: 'Virage',
    unitPriceCents: 4000,
    quantity: 1,
    availableCount: 30,
    eventCapacityTotal: 50,
  );
}

void main() {
  test(
    'persiste et recharge le panier avant 10 minutes',
    () async {
      final storage = MemoryFanCartStorage();

      var now = DateTime.utc(
        2026,
        9,
        4,
        20,
      );

      final first = FanCartController(
        storage: storage,
        now: () => now,
        scheduleExpiryTimers: false,
      );

      await first.ready;
      await first.addItem(makeItem());

      expect(storage.writeCount, 1);
      expect(
        cartValue(first.state).items,
        hasLength(1),
      );

      first.dispose();

      now = now.add(
        const Duration(minutes: 9),
      );

      final second = FanCartController(
        storage: storage,
        now: () => now,
        scheduleExpiryTimers: false,
      );

      await second.ready;

      expect(
        cartValue(second.state).items,
        hasLength(1),
      );
      expect(
        cartValue(second.state).remaining(now),
        const Duration(minutes: 1),
      );

      second.dispose();
    },
  );

  test(
    'supprime le panier à partir de 10 minutes',
    () async {
      final storage = MemoryFanCartStorage();

      var now = DateTime.utc(
        2026,
        9,
        4,
        20,
      );

      final first = FanCartController(
        storage: storage,
        now: () => now,
        scheduleExpiryTimers: false,
      );

      await first.ready;
      await first.addItem(makeItem());
      first.dispose();

      now = now.add(
        const Duration(minutes: 10),
      );

      final expired = FanCartController(
        storage: storage,
        now: () => now,
        scheduleExpiryTimers: false,
      );

      await expired.ready;

      expect(
        cartValue(expired.state).isEmpty,
        isTrue,
      );
      expect(storage.value, isNull);
      expect(storage.clearCount, 1);

      expired.dispose();
    },
  );

  test(
    'une modification à 9 minutes ne repousse pas expiration',
    () async {
      final storage = MemoryFanCartStorage();

      final startedAt = DateTime.utc(
        2026,
        9,
        4,
        20,
      );

      var now = startedAt;

      final controller = FanCartController(
        storage: storage,
        now: () => now,
        scheduleExpiryTimers: false,
      );

      await controller.ready;
      await controller.addItem(makeItem());

      final initialExpiry = cartValue(controller.state).expiresAt;

      expect(
        initialExpiry,
        startedAt.add(
          const Duration(minutes: 10),
        ),
      );

      now = startedAt.add(
        const Duration(minutes: 9),
      );

      await controller.updateQuantity(
        'tariff-1',
        2,
      );

      expect(
        cartValue(controller.state).expiresAt,
        initialExpiry,
      );

      expect(
        storage.value?['expires_at'],
        initialExpiry?.toUtc().toIso8601String(),
      );

      controller.dispose();

      now = startedAt.add(
        const Duration(minutes: 10),
      );

      final reloaded = FanCartController(
        storage: storage,
        now: () => now,
        scheduleExpiryTimers: false,
      );

      await reloaded.ready;

      expect(
        cartValue(reloaded.state).isEmpty,
        isTrue,
      );

      expect(storage.value, isNull);

      reloaded.dispose();
    },
  );
}
