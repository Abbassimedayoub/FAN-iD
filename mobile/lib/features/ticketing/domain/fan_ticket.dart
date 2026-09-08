class FanTicket {
  const FanTicket({
    required this.id,
    required this.status,
    required this.eventId,
    required this.eventName,
    required this.eventStartsAt,
    required this.eventStatus,
    required this.postponementReason,
    required this.postponedFromStartsAt,
    required this.postponedToStartsAt,
    required this.ticketCategoryName,
    required this.issuedAt,
  });

  final String id;
  final String status;
  final String eventId;
  final String eventName;
  final DateTime eventStartsAt;
  final String eventStatus;
  final String? postponementReason;
  final DateTime? postponedFromStartsAt;
  final DateTime? postponedToStartsAt;
  final String ticketCategoryName;
  final DateTime issuedAt;

  factory FanTicket.fromJson(Map<String, dynamic> json) {
    String requiredString(String key) {
      final value = json[key]?.toString().trim();

      if (value == null || value.isEmpty) {
        throw FormatException('Champ billet manquant : $key');
      }

      return value;
    }

    String? optionalString(String key) {
      final value = json[key]?.toString().trim();
      return value == null || value.isEmpty ? null : value;
    }

    DateTime? optionalDate(String key) {
      final value = optionalString(key);
      return value == null ? null : DateTime.parse(value);
    }

    return FanTicket(
      id: requiredString('id'),
      status: requiredString('status').toUpperCase(),
      eventId: requiredString('event_id'),
      eventName: requiredString('event_name'),
      eventStartsAt: DateTime.parse(requiredString('event_starts_at')),
      eventStatus:
          (optionalString('event_status') ?? 'PUBLISHED').toUpperCase(),
      postponementReason: optionalString('postponement_reason'),
      postponedFromStartsAt: optionalDate('postponed_from_starts_at'),
      postponedToStartsAt: optionalDate('postponed_to_starts_at'),
      ticketCategoryName: requiredString('ticket_category_name'),
      issuedAt: DateTime.parse(requiredString('created_at')),
    );
  }

  bool get isValid => status == 'VALID';
  bool get isPostponed => eventStatus == 'POSTPONED';

  DateTime get effectiveStartsAt => postponedToStartsAt ?? eventStartsAt;

  String get statusLabel {
    switch (status) {
      case 'VALID':
        return 'Valide';
      case 'USED':
        return 'Utilisé';
      case 'VOID':
        return 'Annulé';
      default:
        return status;
    }
  }
}

class FanTicketQr {
  const FanTicketQr({
    required this.token,
    required this.expiresAt,
    required this.refreshAfterSeconds,
  });

  final String token;
  final DateTime expiresAt;
  final int refreshAfterSeconds;

  factory FanTicketQr.fromJson(Map<String, dynamic> json) {
    final token = json['token']?.toString().trim() ?? '';
    final expiresAtValue = json['expires_at']?.toString();
    final refreshAfter = json['refresh_after_seconds'];

    if (token.isEmpty || expiresAtValue == null || refreshAfter is! int) {
      throw const FormatException('QR dynamique invalide.');
    }

    return FanTicketQr(
      token: token,
      expiresAt: DateTime.parse(expiresAtValue).toUtc(),
      refreshAfterSeconds: refreshAfter,
    );
  }
}
