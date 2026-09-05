import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/fan_cart_storage.dart';
import '../../domain/fan_cart.dart';

class FanCartController extends StateNotifier<AsyncValue<FanCart>> {
  FanCartController({
    required FanCartStorage storage,
    DateTime Function()? now,
    bool scheduleExpiryTimers = true,
  })  : _storage = storage,
        _now = now ?? _utcNow,
        _scheduleExpiryTimers = scheduleExpiryTimers,
        super(const AsyncLoading()) {
    _readyFuture = _load();
  }

  final FanCartStorage _storage;
  final DateTime Function() _now;
  final bool _scheduleExpiryTimers;

  late final Future<void> _readyFuture;

  Timer? _expiryTimer;

  static DateTime _utcNow() => DateTime.now().toUtc();

  Future<void> get ready => _readyFuture;

  Future<void> _load() async {
    try {
      final raw = await _storage.read();

      if (raw == null) {
        state = AsyncData(FanCart.empty());
        return;
      }

      final cart = FanCart.fromJson(raw);
      final now = _now();

      if (cart.isExpired(now)) {
        await _storage.clear();
        state = AsyncData(FanCart.empty());
        return;
      }

      state = AsyncData(cart);
      _scheduleExpiry(cart);
    } catch (error, stackTrace) {
      state = AsyncError(
        error,
        stackTrace,
      );
    }
  }

  Future<FanCart> _currentCart() async {
    await _readyFuture;

    final data = state.when<FanCart?>(
      data: (cart) => cart,
      loading: () => null,
      error: (_, __) => null,
    );

    if (data == null) {
      throw StateError(
        'Le panier local n’est pas disponible.',
      );
    }

    final current = data;

    if (current.isExpired(_now())) {
      await clearCart();
      return FanCart.empty();
    }

    return current;
  }

  Future<void> addItem(
    FanCartItem item,
  ) async {
    final current = await _currentCart();

    final next = current.addItem(
      item,
      now: _now(),
    );

    await _save(next);
  }

  Future<void> updateQuantity(
    String ticketCategoryId,
    int quantity,
  ) async {
    final current = await _currentCart();

    final next = current.updateQuantity(
      ticketCategoryId,
      quantity,
      now: _now(),
    );

    await _save(next);
  }

  Future<void> removeItem(
    String ticketCategoryId,
  ) async {
    final current = await _currentCart();

    final next = current.removeItem(
      ticketCategoryId,
      now: _now(),
    );

    await _save(next);
  }

  Future<int> removeItemsForUnavailableEvents(
    Iterable<String> eventIds,
  ) async {
    final current = await _currentCart();
    final ids = eventIds.toSet();

    final next = current.removeItemsForEvents(ids);
    final removedCount = current.items.length - next.items.length;

    if (removedCount == 0) {
      return 0;
    }

    await _save(next);
    return removedCount;
  }

  Future<void> clearCart() async {
    _expiryTimer?.cancel();
    _expiryTimer = null;

    await _storage.clear();

    state = AsyncData(FanCart.empty());
  }

  Future<void> _save(
    FanCart cart,
  ) async {
    if (cart.isEmpty) {
      await _storage.clear();
    } else {
      await _storage.write(
        cart.toJson(),
      );
    }

    state = AsyncData(cart);
    _scheduleExpiry(cart);
  }

  void _scheduleExpiry(
    FanCart cart,
  ) {
    _expiryTimer?.cancel();
    _expiryTimer = null;

    if (!_scheduleExpiryTimers || cart.isEmpty || cart.expiresAt == null) {
      return;
    }

    final delay = cart.expiresAt!.difference(_now());

    if (delay.inMicroseconds <= 0) {
      unawaited(_expireIfNeeded());
      return;
    }

    _expiryTimer = Timer(
      delay,
      () {
        unawaited(_expireIfNeeded());
      },
    );
  }

  Future<void> _expireIfNeeded() async {
    final data = state.when<FanCart?>(
      data: (cart) => cart,
      loading: () => null,
      error: (_, __) => null,
    );

    if (data == null) {
      return;
    }

    final cart = data;

    if (cart.isExpired(_now())) {
      await clearCart();
      return;
    }

    _scheduleExpiry(cart);
  }

  @override
  void dispose() {
    _expiryTimer?.cancel();
    super.dispose();
  }
}

final fanCartControllerProvider = StateNotifierProvider.family<
    FanCartController, AsyncValue<FanCart>, String>(
  (ref, ownerKey) {
    return FanCartController(
      storage: HiveFanCartStorage(
        ownerKey: ownerKey,
      ),
    );
  },
);
