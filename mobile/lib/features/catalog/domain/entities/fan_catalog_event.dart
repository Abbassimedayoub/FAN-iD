import 'fan_catalog_ticket_category.dart';

class FanCatalogEvent {
  const FanCatalogEvent({
    required this.id,
    required this.categoryId,
    required this.name,
    required this.description,
    required this.startsAt,
    required this.endsAt,
    this.salesStartsAt,
    this.salesEndsAt,
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
    this.ticketCategories = const <FanCatalogTicketCategory>[],
    this.salesOpen = false,
    this.soldOut = false,
    this.catalogStatus = '',
    this.operationalStatus = '',
    this.canAddToCart = false,
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
      salesStartsAt: DateTime.tryParse(
        json['sales_starts_at']?.toString() ?? '',
      ),
      salesEndsAt: DateTime.tryParse(
        json['sales_ends_at']?.toString() ?? '',
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
      ticketCategories: (json['ticket_categories'] is List
              ? json['ticket_categories'] as List
              : const <dynamic>[])
          .whereType<Map>()
          .map(
            (item) => FanCatalogTicketCategory.fromJson(
              Map<String, dynamic>.from(item),
            ),
          )
          .toList(growable: false),
      salesOpen: json['sales_open'] == true,
      soldOut: json['sold_out'] == true,
      catalogStatus: json['catalog_status']?.toString() ?? '',
      operationalStatus: json['operational_status']?.toString() ?? '',
      canAddToCart: json['can_add_to_cart'] == true,
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

  final DateTime? salesStartsAt;
  final DateTime? salesEndsAt;

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
  final List<FanCatalogTicketCategory> ticketCategories;

  final bool salesOpen;
  final bool soldOut;
  final String catalogStatus;
  final String operationalStatus;
  final bool canAddToCart;

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

  String get effectiveCatalogStatus {
    final catalog = catalogStatus.trim().toUpperCase();

    if (catalog.isNotEmpty) {
      return catalog;
    }

    return status.trim().toUpperCase();
  }

  bool get hasCatalogLifecycle => catalogStatus.trim().isNotEmpty;

  String get statusLabel {
    switch (status.trim().toUpperCase()) {
      case 'POSTPONED':
        return 'Reporté';

      case 'SUSPENDED':
        return 'Suspendu';

      case 'CANCELLED':
        return 'Annulé';

      case 'ARCHIVED':
        return 'Archivé';
    }

    switch (effectiveCatalogStatus) {
      case 'COMING_SOON':
        return 'Coming soon';

      case 'SALE_OPEN':
        return 'Vente ouverte';

      case 'SOLD_OUT':
        return 'Complet';

      case 'SALE_CLOSED':
        return 'Vente fermée';

      case 'LIVE':
        return 'En cours';

      case 'ENDED':
        return 'Terminé';

      case 'POSTPONED':
        return 'Reporté';

      case 'SUSPENDED':
        return 'Suspendu';

      case 'CANCELLED':
        return 'Annulé';

      case 'ARCHIVED':
        return 'Archivé';

      // Compatibilité avec un ancien Backend ne fournissant pas encore
      // catalog_status.
      case 'DRAFT':
        return 'Coming soon';

      case 'PUBLISHED':
        return 'Publié';

      default:
        return effectiveCatalogStatus.isEmpty
            ? 'Statut inconnu'
            : effectiveCatalogStatus;
    }
  }

  String get ticketingLabel {
    switch (effectiveCatalogStatus) {
      case 'COMING_SOON':
      case 'DRAFT':
        return 'Billetterie bientôt disponible';

      case 'SOLD_OUT':
        return 'Complet';

      case 'SALE_CLOSED':
        return 'Vente terminée';

      case 'LIVE':
        return 'Événement en cours';

      case 'ENDED':
        return 'Événement terminé';

      case 'POSTPONED':
        return 'Billetterie suspendue pendant le report';

      case 'SUSPENDED':
        return 'Billetterie suspendue';

      case 'CANCELLED':
        return 'Événement annulé';

      default:
        return priceLabel;
    }
  }

  bool get isComingSoon {
    if (effectiveCatalogStatus == 'COMING_SOON') {
      return true;
    }

    // Fallback uniquement pour compatibilité avec l'ancien contrat.
    return !hasCatalogLifecycle && status.toUpperCase() == 'DRAFT';
  }

  bool get isSoldOut {
    if (soldOut || effectiveCatalogStatus == 'SOLD_OUT') {
      return true;
    }

    // Compatibilité avec l'ancien contrat catalogue.
    if (!hasCatalogLifecycle) {
      final structural = status.toUpperCase();

      return (structural == 'PUBLISHED' || structural == 'POSTPONED') &&
          ticketCategoryCount > 0 &&
          availableTicketCategoryCount == 0;
    }

    return false;
  }

  bool get isSaleOpen => salesOpen && effectiveCatalogStatus == 'SALE_OPEN';

  bool get canPurchaseTickets {
    if (hasCatalogLifecycle) {
      return canAddToCart && isSaleOpen && !isSoldOut;
    }

    // Compatibilité uniquement avec un ancien contrat API ne fournissant
    // pas encore catalog_status / sales_open.
    return canAddToCart && !isSoldOut;
  }

  bool get isPostponed => status.toUpperCase() == 'POSTPONED';
}
