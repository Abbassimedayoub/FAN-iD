from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Event
from apps.core.exceptions import ConflictError, NotFoundBusinessError

from ..models import EventAdmissionSession


class EventAdmissionClosedError(ConflictError):
    default_code = "EVENT_ADMISSION_CLOSED"
    default_message = "Les entrées de cet événement ne sont pas ouvertes."


class EventAdmissionUnavailableError(ConflictError):
    default_code = "EVENT_ADMISSION_UNAVAILABLE"
    default_message = (
        "Les entrées ne peuvent pas être ouvertes pour cet événement."
    )


def _event_can_open_admission(event: Event) -> bool:
    return event.status == Event.PUBLISHED or (
        event.status == Event.POSTPONED
        and event.postponed_to_starts_at is not None
        and event.postponed_to_ends_at is not None
    )


def _locked_event(event_id: UUID) -> Event:
    event = Event.objects.select_for_update().filter(pk=event_id).first()
    if event is None:
        raise NotFoundBusinessError(code="EVENT_NOT_FOUND")
    return event


def current_event_admission_session(*, event: Event):
    """
    Retourne uniquement une session encore valable pour la programmation
    actuelle. Un report rend donc automatiquement l'ancienne session inactive.
    """
    if not _event_can_open_admission(event):
        return None

    return EventAdmissionSession.objects.filter(
        event=event,
        closed_at__isnull=True,
        scheduled_starts_at=event.starts_at,
    ).first()


@transaction.atomic
def open_event_admission(*, event_id: UUID, opened_by_id: UUID, now=None):
    event = _locked_event(event_id)

    if not _event_can_open_admission(event):
        raise EventAdmissionUnavailableError()

    moment = now or timezone.now()
    active = (
        EventAdmissionSession.objects.select_for_update()
        .filter(event=event, closed_at__isnull=True)
        .first()
    )

    if active is not None and active.scheduled_starts_at == event.starts_at:
        return active

    # Une session d'une ancienne programmation est invalidée, avec une trace
    # explicite, avant l'ouverture de la session de la nouvelle date.
    if active is not None:
        active.closed_at = moment
        active.closed_by_id = opened_by_id
        active.save(update_fields=["closed_at", "closed_by"])

    return EventAdmissionSession.objects.create(
        event=event,
        opened_at=moment,
        scheduled_starts_at=event.starts_at,
        opened_by_id=opened_by_id,
    )


@transaction.atomic
def close_event_admission(*, event_id: UUID, closed_by_id: UUID, now=None):
    _locked_event(event_id)

    active = EventAdmissionSession.objects.filter(
        event_id=event_id,
        closed_at__isnull=True,
    ).first()
    if active is None:
        return None

    active.closed_at = now or timezone.now()
    active.closed_by_id = closed_by_id
    active.save(update_fields=["closed_at", "closed_by"])
    return active


def require_event_admission_open(*, event_id: UUID) -> None:
    event = _locked_event(event_id)

    if current_event_admission_session(event=event) is None:
        raise EventAdmissionClosedError()


@transaction.atomic
def close_event_admission_automatically(*, event_id: UUID, now=None):
    """
    Ferme une session lors de la clôture automatique de l'événement.

    Aucun faux utilisateur n'est attribué : `closed_automatically` constitue
    la trace d'audit explicite de cette fermeture système.
    """
    _locked_event(event_id)

    active = (
        EventAdmissionSession.objects.select_for_update()
        .filter(
            event_id=event_id,
            closed_at__isnull=True,
        )
        .first()
    )
    if active is None:
        return None

    active.closed_at = now or timezone.now()
    active.closed_by_id = None
    active.closed_automatically = True
    active.save(
        update_fields=[
            "closed_at",
            "closed_by",
            "closed_automatically",
        ]
    )
    return active
