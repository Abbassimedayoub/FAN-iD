import 'entities/scanner_assigned_event.dart';

enum ScannerEventDateFilter {
  upcoming,
  past,
  all,
}

enum ScannerEventStatusFilter {
  all,
  published,
  postponed,
  suspended,
  cancelled,
}

DateTime? scannerEventEffectiveStartsAt(ScannerAssignedEvent event) =>
    event.postponedToStartsAt ?? event.startsAt;

List<ScannerAssignedEvent> filterAndSortScannerEvents(
  Iterable<ScannerAssignedEvent> events, {
  required ScannerEventDateFilter dateFilter,
  required ScannerEventStatusFilter statusFilter,
  DateTime? now,
}) {
  final reference = now ?? DateTime.now();

  bool matchesStatus(ScannerAssignedEvent event) {
    switch (statusFilter) {
      case ScannerEventStatusFilter.all:
        return true;
      case ScannerEventStatusFilter.published:
        return event.status.toUpperCase() == 'PUBLISHED';
      case ScannerEventStatusFilter.postponed:
        return event.status.toUpperCase() == 'POSTPONED';
      case ScannerEventStatusFilter.suspended:
        return event.status.toUpperCase() == 'SUSPENDED';
      case ScannerEventStatusFilter.cancelled:
        return event.status.toUpperCase() == 'CANCELLED';
    }
  }

  bool isUpcoming(ScannerAssignedEvent event) {
    final startsAt = scannerEventEffectiveStartsAt(event);
    return startsAt == null || !startsAt.isBefore(reference);
  }

  final filtered = events.where((event) {
    if (!matchesStatus(event)) {
      return false;
    }

    switch (dateFilter) {
      case ScannerEventDateFilter.upcoming:
        return isUpcoming(event);
      case ScannerEventDateFilter.past:
        return !isUpcoming(event);
      case ScannerEventDateFilter.all:
        return true;
    }
  }).toList();

  filtered.sort((left, right) {
    final leftUpcoming = isUpcoming(left);
    final rightUpcoming = isUpcoming(right);

    if (dateFilter == ScannerEventDateFilter.all &&
        leftUpcoming != rightUpcoming) {
      return leftUpcoming ? -1 : 1;
    }

    final leftDate = scannerEventEffectiveStartsAt(left);
    final rightDate = scannerEventEffectiveStartsAt(right);

    if (leftDate == null || rightDate == null) {
      if (leftDate == null && rightDate == null) {
        return left.name.compareTo(right.name);
      }
      return leftDate == null ? 1 : -1;
    }

    final comparison = leftDate.compareTo(rightDate);
    return dateFilter == ScannerEventDateFilter.past ? -comparison : comparison;
  });

  return filtered;
}
