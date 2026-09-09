import 'fan_ticket.dart';

enum FanTicketDateFilter {
  upcoming,
  past,
  all,
}

enum FanTicketStatusFilter {
  all,
  valid,
  used,
  voided,
}

List<FanTicket> filterAndSortFanTickets(
  Iterable<FanTicket> tickets, {
  required FanTicketDateFilter dateFilter,
  required FanTicketStatusFilter statusFilter,
  DateTime? now,
}) {
  final reference = now ?? DateTime.now();

  bool matchesStatus(FanTicket ticket) {
    switch (statusFilter) {
      case FanTicketStatusFilter.all:
        return true;
      case FanTicketStatusFilter.valid:
        return ticket.status == 'VALID';
      case FanTicketStatusFilter.used:
        return ticket.status == 'USED';
      case FanTicketStatusFilter.voided:
        return ticket.status == 'VOID';
    }
  }

  bool isUpcoming(FanTicket ticket) =>
      !ticket.effectiveStartsAt.isBefore(reference);

  final filtered = tickets.where((ticket) {
    if (!matchesStatus(ticket)) {
      return false;
    }

    switch (dateFilter) {
      case FanTicketDateFilter.upcoming:
        return isUpcoming(ticket);
      case FanTicketDateFilter.past:
        return !isUpcoming(ticket);
      case FanTicketDateFilter.all:
        return true;
    }
  }).toList();

  filtered.sort((left, right) {
    final leftUpcoming = isUpcoming(left);
    final rightUpcoming = isUpcoming(right);

    if (dateFilter == FanTicketDateFilter.all &&
        leftUpcoming != rightUpcoming) {
      return leftUpcoming ? -1 : 1;
    }

    final comparison =
        left.effectiveStartsAt.compareTo(right.effectiveStartsAt);

    return dateFilter == FanTicketDateFilter.past ? -comparison : comparison;
  });

  return filtered;
}
