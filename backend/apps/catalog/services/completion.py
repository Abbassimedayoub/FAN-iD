from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.core.outbox.publisher import publish_event

from ..events import AGGREGATE_EVENT, CATALOG_EVENT_COMPLETED, event_lifecycle_payload
from ..models import Event

AUTO_COMPLETION_REASON = "Clôturé automatiquement à la fin de l’événement."


def _can_be_completed(event: Event, *, now) -> bool:
    if event.ends_at > now:
        return False

    if event.status == Event.PUBLISHED:
        return True

    return event.status == Event.POSTPONED and event.postponed_to_ends_at is not None


@transaction.atomic
def complete_event_if_elapsed(
    *,
    event_id: UUID,
    now=None,
) -> bool:
    """Clôture un événement terminé, une seule fois, avec outbox atomique."""
    moment = now or timezone.now()

    event = Event.objects.select_for_update().filter(pk=event_id).first()
    if event is None or not _can_be_completed(event, now=moment):
        return False

    event.status = Event.COMPLETED
    event.lifecycle_reason = AUTO_COMPLETION_REASON
    event.lifecycle_changed_at = moment
    event.save(
        update_fields=[
            "status",
            "lifecycle_reason",
            "lifecycle_changed_at",
        ]
    )

    publish_event(
        event_type=CATALOG_EVENT_COMPLETED,
        aggregate_type=AGGREGATE_EVENT,
        aggregate_id=event.id,
        payload=event_lifecycle_payload(
            status=event.status,
            reason=AUTO_COMPLETION_REASON,
            notify_buyers=False,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
        ),
    )
    return True


def complete_elapsed_events(*, now=None) -> int:
    """Traite les événements terminés, y compris ceux finissant après minuit."""
    moment = now or timezone.now()

    event_ids = list(
        Event.objects.filter(
            ends_at__lte=moment,
            status__in=[
                Event.PUBLISHED,
                Event.POSTPONED,
            ],
        )
        .order_by("ends_at", "pk")
        .values_list("pk", flat=True)
    )

    completed = 0
    for event_id in event_ids:
        completed += int(
            complete_event_if_elapsed(
                event_id=event_id,
                now=moment,
            )
        )
    return completed
