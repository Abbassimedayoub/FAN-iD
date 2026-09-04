class FanCatalogEvent {
  const FanCatalogEvent({
    required this.id,
    required this.categoryId,
    required this.name,
    required this.description,
    required this.startsAt,
    required this.endsAt,
    required this.postponedFromStartsAt,
    required this.postponedFromEndsAt,
    required this.postponedToStartsAt,
    required this.postponedToEndsAt,
    required this.venue,
    required this.capacityTotal,
    required this.imageUrl,
    this.minPriceCents,
    this.ticketCategoryCount = 0,
    this.availableTicketCategoryCount = 0,
    required this.status,
    required this.publishedAt,
    required this.lifecycleReason,
    required this.lifecycleChangedAt,
  });

  factory FanCatalogEvent.fromJson(Map<String, dynamic> json) {
    return FanCatalogEvent(
      id: json['id']?.toString() ?? '',
      categoryId: json['category_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      description: json['description']?.toString() ?? '',
      startsAt: DateTime.tryParse(
        json['starts_at']?.toString() ?? '',
      ),
      endsAt: DateTime.tryParse(
        json['ends_at']?.toString() ?? '',
      ),
      postponedFromStartsAt: DateTime.tryParse(
        json['postponed_from_starts_at']?.toString() ?? '',
      ),
      postponedFromEndsAt: DateTime.tryParse(
        json['postponed_from_ends_at']?.toString() ?? '',
      ),
      postponedToStartsAt: DateTime.tryParse(
        json['postponed_to_starts_at']?.toString() ?? '',
      ),
      postponedToEndsAt: DateTime.tryParse(
        json['postponed_to_ends_at']?.toString() ?? '',
      ),
      venue: json['venue']?.toString() ?? '',
      capacityTotal: json['capacity_total'] is int
          ? json['capacity_total'] as int
          : int.tryParse(
              json['capacity_total']?.toString() ?? '',
            ),
      imageUrl: json['image_url']?.toString(),
      minPriceCents: json['min_price_cents'] is int
          ? json['min_price_cents'] as int
          : int.tryParse(
              json['min_price_cents']?.toString() ?? '',
            ),
      ticketCategoryCount: json['ticket_category_count'] is int
          ? json['ticket_category_count'] as int
          : int.tryParse(
                json['ticket_category_count']?.toString() ?? '',
              ) ??
              0,
      availableTicketCategoryCount:
          json['available_ticket_category_count'] is int
              ? json['available_ticket_category_count'] as int
              : int.tryParse(
                    json['available_ticket_category_count']?.toString() ?? '',
                  ) ??
                  0,
      status: json['status']?.toString() ?? '',
      publishedAt: DateTime.tryParse(
        json['published_at']?.toString() ?? '',
      ),
      lifecycleReason: json['lifecycle_reason']?.toString() ?? '',
      lifecycleChangedAt: DateTime.tryParse(
        json['lifecycle_changed_at']?.toString() ?? '',
      ),
    );
  }

  final String id;
  final String categoryId;
  final String name;
  final String description;
  final DateTime? startsAt;
  final DateTime? endsAt;

  final DateTime? postponedFromStartsAt;
  final DateTime? postponedFromEndsAt;
  final DateTime? postponedToStartsAt;
  final DateTime? postponedToEndsAt;

  final String venue;
  final int? capacityTotal;
  final String? imageUrl;

  final int? minPriceCents;
  final int ticketCategoryCount;
  final int availableTicketCategoryCount;

  final String status;
  final DateTime? publishedAt;
  final String lifecycleReason;
  final DateTime? lifecycleChangedAt;

  String get priceLabel {
    if (ticketCategoryCount > 0 && availableTicketCategoryCount == 0) {
      return 'Complet';
    }

    final cents = minPriceCents;

    if (cents == null) {
      return 'Tarif à venir';
    }

    final euros = cents ~/ 100;
    final remainder = cents % 100;

    final formatted = remainder == 0
        ? '$euros €'
        : '$euros,${remainder.toString().padLeft(2, '0')} €';

    if (availableTicketCategoryCount > 1) {
      return 'À partir de $formatted';
    }

    return formatted;
  }

  String get statusLabel {
    switch (status.toUpperCase()) {
      case 'PUBLISHED':
        return 'Publié';

      case 'POSTPONED':
        return 'Reporté';

      case 'SUSPENDED':
        return 'Suspendu';

      case 'CANCELLED':
        return 'Annulé';

      case 'ARCHIVED':
        return 'Archivé';

      case 'DRAFT':
        return 'Coming soon';

      default:
        return status.isEmpty ? 'Statut inconnu' : status;
    }
  }

  bool get isPostponed => status.toUpperCase() == 'POSTPONED';
}
