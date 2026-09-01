class ScannerAssignedEvent {
  const ScannerAssignedEvent({
    required this.assignmentId,
    required this.id,
    required this.name,
    required this.startsAt,
    required this.endsAt,
    this.postponedFromStartsAt,
    this.postponedFromEndsAt,
    this.postponedToStartsAt,
    this.postponedToEndsAt,
    required this.venue,
    required this.status,
    required this.lifecycleReason,
  });

  factory ScannerAssignedEvent.fromJson(
    Map<String, dynamic> json,
  ) {
    return ScannerAssignedEvent(
      assignmentId: json['assignment_id']?.toString() ?? '',
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
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
      status: json['status']?.toString() ?? '',
      lifecycleReason: json['lifecycle_reason']?.toString() ?? '',
    );
  }

  final String assignmentId;
  final String id;
  final String name;
  final DateTime? startsAt;
  final DateTime? endsAt;
  final DateTime? postponedFromStartsAt;
  final DateTime? postponedFromEndsAt;
  final DateTime? postponedToStartsAt;
  final DateTime? postponedToEndsAt;
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

  bool get accessInterrupted {
    switch (status.toUpperCase()) {
      case 'SUSPENDED':
      case 'CANCELLED':
      case 'ARCHIVED':
        return true;
      default:
        return false;
    }
  }
}
