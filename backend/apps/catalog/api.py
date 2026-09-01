"""
Interface publique de lecture du contexte catalog.

Ce module expose uniquement les informations nécessaires aux
consommateurs externes et au portail scanner.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from .models import Event, EventScannerAssignment


@dataclass(
    frozen=True,
    slots=True,
)
class EventNotificationSummary:
    id: uuid.UUID
    organizer_id: uuid.UUID | None
    name: str
    starts_at: datetime
    ends_at: datetime
    venue: str
    status: str
    lifecycle_reason: str
    lifecycle_changed_at: datetime | None


@dataclass(
    frozen=True,
    slots=True,
)
class ScannerPortalEventSummary:
    assignment_id: uuid.UUID
    assigned_at: datetime
    id: uuid.UUID
    organizer_id: uuid.UUID
    name: str
    starts_at: datetime
    ends_at: datetime
    postponed_from_starts_at: datetime | None
    postponed_from_ends_at: datetime | None
    postponed_to_starts_at: datetime | None
    postponed_to_ends_at: datetime | None
    venue: str
    status: str
    lifecycle_reason: str
    lifecycle_changed_at: datetime | None


def get_event_notification_summary(
    *,
    event_id: uuid.UUID,
) -> EventNotificationSummary | None:
    event = (
        Event.objects.filter(
            pk=event_id,
        )
        .only(
            "id",
            "organizer_id",
            "name",
            "starts_at",
            "ends_at",
            "venue",
            "status",
            "lifecycle_reason",
            "lifecycle_changed_at",
        )
        .first()
    )

    if event is None:
        return None

    return EventNotificationSummary(
        id=event.pk,
        organizer_id=event.organizer_id,
        name=event.name,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        venue=event.venue,
        status=event.status,
        lifecycle_reason=event.lifecycle_reason,
        lifecycle_changed_at=event.lifecycle_changed_at,
    )


def list_active_scanner_ids_for_event(
    *,
    event_id: uuid.UUID,
) -> tuple[uuid.UUID, ...]:
    return tuple(
        EventScannerAssignment.objects.filter(
            event_id=event_id,
            unassigned_at__isnull=True,
        )
        .order_by(
            "created_at",
            "pk",
        )
        .values_list(
            "scanner_id",
            flat=True,
        )
    )


def list_scanner_portal_events(
    *,
    scanner_id: uuid.UUID,
    organizer_id: uuid.UUID,
) -> tuple[ScannerPortalEventSummary, ...]:
    """
    Retourne exclusivement les affectations actives du scanner.

    Le double filtre scanner + organizer empêche qu'un UUID de scanner
    soit utilisé pour lire un événement d'un autre organisateur.
    """

    assignments = (
        EventScannerAssignment.objects.filter(
            scanner_id=scanner_id,
            unassigned_at__isnull=True,
            event__organizer_id=organizer_id,
        )
        .select_related(
            "event",
        )
        .order_by(
            "event__starts_at",
            "created_at",
            "pk",
        )
    )

    return tuple(
        ScannerPortalEventSummary(
            assignment_id=assignment.pk,
            assigned_at=assignment.created_at,
            id=assignment.event.pk,
            organizer_id=assignment.event.organizer_id,
            name=assignment.event.name,
            starts_at=assignment.event.starts_at,
            ends_at=assignment.event.ends_at,
            postponed_from_starts_at=(assignment.event.postponed_from_starts_at),
            postponed_from_ends_at=(assignment.event.postponed_from_ends_at),
            postponed_to_starts_at=(assignment.event.postponed_to_starts_at),
            postponed_to_ends_at=(assignment.event.postponed_to_ends_at),
            venue=assignment.event.venue,
            status=assignment.event.status,
            lifecycle_reason=(assignment.event.lifecycle_reason),
            lifecycle_changed_at=(assignment.event.lifecycle_changed_at),
        )
        for assignment in assignments
    )
