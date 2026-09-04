class FanCatalogTicketCategory {
  const FanCatalogTicketCategory({
    required this.id,
    required this.name,
    required this.unitPriceCents,
    required this.availableCount,
  });

  factory FanCatalogTicketCategory.fromJson(
    Map<String, dynamic> json,
  ) {
    int intValue(Object? value) {
      if (value is int) {
        return value;
      }

      return int.tryParse(
            value?.toString() ?? '',
          ) ??
          0;
    }

    return FanCatalogTicketCategory(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      unitPriceCents: intValue(
        json['unit_price_cents'],
      ),
      availableCount: intValue(
        json['available_count'],
      ),
    );
  }

  final String id;
  final String name;
  final int unitPriceCents;
  final int availableCount;

  bool get isAvailable => availableCount > 0;

  String get priceLabel {
    final euros = unitPriceCents ~/ 100;
    final cents = unitPriceCents % 100;

    if (cents == 0) {
      return '$euros €';
    }

    return '$euros,${cents.toString().padLeft(2, '0')} €';
  }
}
