class FanCartValidationException implements Exception {
  const FanCartValidationException(this.message);

  final String message;

  @override
  String toString() => message;
}

class FanCartItem {
  const FanCartItem({
    required this.eventId,
    required this.eventName,
    required this.ticketCategoryId,
    required this.ticketCategoryName,
    required this.unitPriceCents,
    required this.quantity,
    required this.availableCount,
    required this.eventCapacityTotal,
  });

  factory FanCartItem.fromJson(
    Map<String, dynamic> json,
  ) {
    int intValue(
      Object? value, {
      int fallback = 0,
    }) {
      if (value is int) {
        return value;
      }

      return int.tryParse(
            value?.toString() ?? '',
          ) ??
          fallback;
    }

    int? nullableIntValue(Object? value) {
      if (value == null) {
        return null;
      }

      if (value is int) {
        return value;
      }

      return int.tryParse(value.toString());
    }

    return FanCartItem(
      eventId: json['event_id']?.toString() ?? '',
      eventName: json['event_name']?.toString() ?? '',
      ticketCategoryId: json['ticket_category_id']?.toString() ?? '',
      ticketCategoryName: json['ticket_category_name']?.toString() ?? '',
      unitPriceCents: intValue(
        json['unit_price_cents'],
      ),
      quantity: intValue(
        json['quantity'],
        fallback: 1,
      ),
      availableCount: intValue(
        json['available_count'],
      ),
      eventCapacityTotal: nullableIntValue(
        json['event_capacity_total'],
      ),
    );
  }

  final String eventId;
  final String eventName;
  final String ticketCategoryId;
  final String ticketCategoryName;
  final int unitPriceCents;
  final int quantity;
  final int availableCount;
  final int? eventCapacityTotal;

  int get lineTotalCents => unitPriceCents * quantity;

  FanCartItem copyWith({
    int? quantity,
    int? availableCount,
    int? eventCapacityTotal,
  }) {
    return FanCartItem(
      eventId: eventId,
      eventName: eventName,
      ticketCategoryId: ticketCategoryId,
      ticketCategoryName: ticketCategoryName,
      unitPriceCents: unitPriceCents,
      quantity: quantity ?? this.quantity,
      availableCount: availableCount ?? this.availableCount,
      eventCapacityTotal: eventCapacityTotal ?? this.eventCapacityTotal,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'event_id': eventId,
      'event_name': eventName,
      'ticket_category_id': ticketCategoryId,
      'ticket_category_name': ticketCategoryName,
      'unit_price_cents': unitPriceCents,
      'quantity': quantity,
      'available_count': availableCount,
      'event_capacity_total': eventCapacityTotal,
    };
  }
}

class FanCart {
  FanCart({
    required List<FanCartItem> items,
    required this.expiresAt,
  }) : items = List<FanCartItem>.unmodifiable(items);

  factory FanCart.empty() {
    return FanCart(
      items: const <FanCartItem>[],
      expiresAt: null,
    );
  }

  factory FanCart.fromJson(
    Map<String, dynamic> json,
  ) {
    final rawItems = json['items'];

    final items = rawItems is List
        ? rawItems
            .whereType<Map>()
            .map(
              (item) => FanCartItem.fromJson(
                Map<String, dynamic>.from(item),
              ),
            )
            .toList(growable: false)
        : const <FanCartItem>[];

    return FanCart(
      items: items,
      expiresAt: DateTime.tryParse(
        json['expires_at']?.toString() ?? '',
      ),
    );
  }

  static const Duration ttl = Duration(
    minutes: 10,
  );

  final List<FanCartItem> items;
  final DateTime? expiresAt;

  bool get isEmpty => items.isEmpty;

  int get totalQuantity => items.fold<int>(
        0,
        (total, item) => total + item.quantity,
      );

  int get totalCents => items.fold<int>(
        0,
        (total, item) => total + item.lineTotalCents,
      );

  bool isExpired(DateTime now) {
    final expiry = expiresAt;

    if (expiry == null || items.isEmpty) {
      return false;
    }

    return !now.isBefore(expiry);
  }

  Duration remaining(DateTime now) {
    final expiry = expiresAt;

    if (expiry == null || items.isEmpty) {
      return Duration.zero;
    }

    final remaining = expiry.difference(now);

    if (remaining.isNegative) {
      return Duration.zero;
    }

    return remaining;
  }

  FanCart addItem(
    FanCartItem incoming, {
    required DateTime now,
  }) {
    _validatePositiveQuantity(incoming.quantity);

    if (incoming.availableCount <= 0) {
      throw const FanCartValidationException(
        'Ce tarif est complet.',
      );
    }

    final index = items.indexWhere(
      (item) => item.ticketCategoryId == incoming.ticketCategoryId,
    );

    final existing = index >= 0 ? items[index] : null;

    if (existing != null && existing.eventId != incoming.eventId) {
      throw const FanCartValidationException(
        'Tarif de panier incohérent.',
      );
    }

    final quantity = (existing?.quantity ?? 0) + incoming.quantity;

    final nextItem = incoming.copyWith(
      quantity: quantity,
    );

    _validateAvailability(nextItem);
    _validateEventCapacity(
      nextItem,
      replacingTicketCategoryId: incoming.ticketCategoryId,
    );

    final nextItems = List<FanCartItem>.from(items);

    if (index >= 0) {
      nextItems[index] = nextItem;
    } else {
      nextItems.add(nextItem);
    }

    return FanCart(
      items: nextItems,
      expiresAt: _expiryForMutation(now),
    );
  }

  FanCart updateQuantity(
    String ticketCategoryId,
    int quantity, {
    required DateTime now,
  }) {
    _validatePositiveQuantity(quantity);

    final index = items.indexWhere(
      (item) => item.ticketCategoryId == ticketCategoryId,
    );

    if (index < 0) {
      throw const FanCartValidationException(
        'Billet introuvable dans le panier.',
      );
    }

    final nextItem = items[index].copyWith(
      quantity: quantity,
    );

    _validateAvailability(nextItem);
    _validateEventCapacity(
      nextItem,
      replacingTicketCategoryId: ticketCategoryId,
    );

    final nextItems = List<FanCartItem>.from(items);

    nextItems[index] = nextItem;

    return FanCart(
      items: nextItems,
      expiresAt: _expiryForMutation(now),
    );
  }

  FanCart removeItem(
    String ticketCategoryId, {
    required DateTime now,
  }) {
    final nextItems = items
        .where(
          (item) => item.ticketCategoryId != ticketCategoryId,
        )
        .toList(growable: false);

    if (nextItems.length == items.length) {
      return this;
    }

    if (nextItems.isEmpty) {
      return FanCart.empty();
    }

    return FanCart(
      items: nextItems,
      expiresAt: _expiryForMutation(now),
    );
  }

  DateTime _expiryForMutation(
    DateTime now,
  ) {
    final currentExpiry = expiresAt;

    if (items.isEmpty || currentExpiry == null || isExpired(now)) {
      return now.add(ttl);
    }

    return currentExpiry;
  }

  void _validatePositiveQuantity(
    int quantity,
  ) {
    if (quantity <= 0) {
      throw const FanCartValidationException(
        'La quantité doit être supérieure à zéro.',
      );
    }
  }

  void _validateAvailability(
    FanCartItem item,
  ) {
    if (item.quantity > item.availableCount) {
      throw FanCartValidationException(
        'Il ne reste que '
        '${item.availableCount} place(s) '
        'pour ce tarif.',
      );
    }
  }

  void _validateEventCapacity(
    FanCartItem item, {
    required String replacingTicketCategoryId,
  }) {
    final capacity = item.eventCapacityTotal;

    if (capacity == null) {
      return;
    }

    final quantityOnOtherTariffs = items
        .where(
          (existing) =>
              existing.eventId == item.eventId &&
              existing.ticketCategoryId != replacingTicketCategoryId,
        )
        .fold<int>(
          0,
          (total, existing) => total + existing.quantity,
        );

    if (quantityOnOtherTariffs + item.quantity > capacity) {
      throw FanCartValidationException(
        'La quantité dépasse la capacité '
        'de l’événement ($capacity).',
      );
    }
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'items': items.map((item) => item.toJson()).toList(growable: false),
      'expires_at': expiresAt?.toUtc().toIso8601String(),
    };
  }
}
