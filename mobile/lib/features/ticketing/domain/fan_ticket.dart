class FanTicket {
  const FanTicket({
    required this.id,
    required this.status,
    required this.eventId,
    required this.eventName,
    required this.eventStartsAt,
    required this.ticketCategoryName,
    required this.issuedAt,
  });

  final String id;
  final String status;
  final String eventId;
  final String eventName;
  final DateTime eventStartsAt;
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

    return FanTicket(
      id: requiredString('id'),
      status: requiredString('status').toUpperCase(),
      eventId: requiredString('event_id'),
      eventName: requiredString('event_name'),
      eventStartsAt: DateTime.parse(requiredString('event_starts_at')),
      ticketCategoryName: requiredString('ticket_category_name'),
      issuedAt: DateTime.parse(requiredString('created_at')),
    );
  }

  bool get isValid => status == 'VALID';

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
