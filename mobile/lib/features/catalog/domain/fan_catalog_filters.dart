import 'entities/fan_catalog_event.dart';

enum FanCatalogAvailabilityFilter {
  all,
  available,
  full,
}

enum FanCatalogTimeFilter {
  all,
  upcoming,
  ongoing,
  finished,
}

enum FanCatalogTimeState {
  unknown,
  upcoming,
  ongoing,
  finished,
}

abstract final class FanCatalogFilters {
  static bool hasAvailableTickets(
    FanCatalogEvent event,
  ) {
    if (event.hasCatalogLifecycle) {
      return event.canAddToCart &&
          event.salesOpen &&
          !event.isSoldOut &&
          event.availableTicketCategoryCount > 0;
    }

    // Fallback ancien contrat API.
    final status = event.status.toUpperCase();

    return (status == 'PUBLISHED' || status == 'POSTPONED') &&
        event.availableTicketCategoryCount > 0;
  }

  static bool isFull(
    FanCatalogEvent event,
  ) {
    return event.isSoldOut;
  }

  static FanCatalogTimeState timeStateAt(
    FanCatalogEvent event,
    DateTime now,
  ) {
    if (event.hasCatalogLifecycle) {
      switch (event.effectiveCatalogStatus) {
        case 'LIVE':
          return FanCatalogTimeState.ongoing;

        case 'ENDED':
          return FanCatalogTimeState.finished;

        case 'POSTPONED':
        case 'SUSPENDED':
        case 'CANCELLED':
        case 'ARCHIVED':
        case 'DRAFT':
          return FanCatalogTimeState.unknown;
      }
    } else if (event.isComingSoon) {
      return FanCatalogTimeState.unknown;
    }

    DateTime? startsAt;
    DateTime? endsAt;

    if (event.isPostponed) {
      startsAt = event.postponedToStartsAt;
      endsAt = event.postponedToEndsAt;

      if (startsAt == null || endsAt == null) {
        return FanCatalogTimeState.unknown;
      }
    } else {
      startsAt = event.startsAt;
      endsAt = event.endsAt;
    }

    if (startsAt == null || endsAt == null || !endsAt.isAfter(startsAt)) {
      return FanCatalogTimeState.unknown;
    }

    if (now.isBefore(startsAt)) {
      return FanCatalogTimeState.upcoming;
    }

    if (now.isBefore(endsAt)) {
      return FanCatalogTimeState.ongoing;
    }

    return FanCatalogTimeState.finished;
  }

  static List<String> venues(
    Iterable<FanCatalogEvent> events,
  ) {
    final byNormalized = <String, String>{};

    for (final event in events) {
      final venue = event.venue.trim();

      if (venue.isEmpty) {
        continue;
      }

      byNormalized.putIfAbsent(
        venue.toLowerCase(),
        () => venue,
      );
    }

    final result = byNormalized.values.toList();

    result.sort(
      (left, right) => left.toLowerCase().compareTo(right.toLowerCase()),
    );

    return result;
  }

  static List<FanCatalogEvent> apply(
    Iterable<FanCatalogEvent> events, {
    String? venue,
    FanCatalogAvailabilityFilter availability =
        FanCatalogAvailabilityFilter.all,
    FanCatalogTimeFilter time = FanCatalogTimeFilter.all,
    required DateTime now,
  }) {
    final normalizedVenue = venue?.trim().toLowerCase();

    return events.where(
      (event) {
        if (normalizedVenue != null &&
            normalizedVenue.isNotEmpty &&
            event.venue.trim().toLowerCase() != normalizedVenue) {
          return false;
        }

        final matchesAvailability = switch (availability) {
          FanCatalogAvailabilityFilter.all => true,
          FanCatalogAvailabilityFilter.available => hasAvailableTickets(event),
          FanCatalogAvailabilityFilter.full => isFull(event),
        };

        if (!matchesAvailability) {
          return false;
        }

        if (time == FanCatalogTimeFilter.all) {
          return true;
        }

        final state = timeStateAt(
          event,
          now,
        );

        return switch (time) {
          FanCatalogTimeFilter.all => true,
          FanCatalogTimeFilter.upcoming =>
            state == FanCatalogTimeState.upcoming,
          FanCatalogTimeFilter.ongoing => state == FanCatalogTimeState.ongoing,
          FanCatalogTimeFilter.finished =>
            state == FanCatalogTimeState.finished,
        };
      },
    ).toList(growable: false);
  }
}
