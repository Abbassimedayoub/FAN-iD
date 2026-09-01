class OrganizerMobileEvent {
  const OrganizerMobileEvent({
    required this.id,
    required this.name,
    required this.startsAt,
    required this.endsAt,
    required this.venue,
    required this.status,
    required this.lifecycleReason,
  });

  factory OrganizerMobileEvent.fromJson(Map<String, dynamic> json) {
    return OrganizerMobileEvent(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      startsAt: DateTime.tryParse(json['starts_at']?.toString() ?? ''),
      endsAt: DateTime.tryParse(json['ends_at']?.toString() ?? ''),
      venue: json['venue']?.toString() ?? '',
      status: json['status']?.toString() ?? '',
      lifecycleReason: json['lifecycle_reason']?.toString() ?? '',
    );
  }

  final String id;
  final String name;
  final DateTime? startsAt;
  final DateTime? endsAt;
  final String venue;
  final String status;
  final String lifecycleReason;

  String get statusLabel {
    switch (status.toUpperCase()) {
      case 'PUBLISHED':
      case 'ON_TIME':
        return 'À l’heure';

      case 'POSTPONED':
      case 'DELAYED':
        return 'Retardé / reporté';

      case 'SUSPENDED':
        return 'Suspendu';

      case 'CANCELLED':
        return 'Annulé';

      case 'ARCHIVED':
        return 'Archivé';

      case 'DRAFT':
        return 'Brouillon';

      default:
        return status.isEmpty ? 'Statut inconnu' : status;
    }
  }
}
