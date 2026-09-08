from __future__ import annotations

import uuid
from typing import Any

from celery import shared_task
from django.utils import timezone

from apps.catalog.api import get_event_notification_summary
from apps.core.adapters.notifications import build_notification_sender
from apps.ticketing.api import list_ticket_buyer_notification_recipients


def _retry(task: Any, exc: Exception) -> None:
    retries = int(getattr(task.request, "retries", 0))
    raise task.retry(
        exc=exc,
        countdown=min(30 * (2**retries), 600),
    ) from exc


def _postponement_message(event: Any) -> tuple[str, str]:
    subject = f"[FANID] Votre événement est reporté : {event.name}"
    reason = event.lifecycle_reason or "Aucun motif complémentaire n’a été fourni."

    if event.postponed_to_starts_at is not None:
        starts_at = timezone.localtime(event.postponed_to_starts_at)
        schedule = (
            "Nouvelle date : "
            f"{starts_at.strftime('%d/%m/%Y à %H:%M')}\n\n"
            "Votre billet et son QR restent valides pour cette nouvelle date. "
            "Vous n’avez aucune action à effectuer."
        )
    else:
        schedule = (
            "La nouvelle date sera communiquée prochainement. "
            "Votre billet est conservé et restera valable. "
            "Les entrées restent fermées jusqu’à l’annonce de la nouvelle date."
        )

    return subject, f"Motif du report : {reason}\n\n{schedule}"


@shared_task(
    bind=True,
    name="notifying.event_buyer.postponement_emails",
    max_retries=5,
)
def send_event_buyer_postponement_emails(
    self: Any,
    *,
    event_id: str,
) -> dict[str, Any]:
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        return {"sent": False, "reason": "invalid_identifier"}

    event = get_event_notification_summary(event_id=event_uuid)
    if event is None:
        return {"sent": False, "reason": "event_missing"}

    subject, details = _postponement_message(event)
    recipients = list_ticket_buyer_notification_recipients(event_id=event_uuid)
    sender = build_notification_sender()
    sent = 0

    try:
        for recipient in recipients:
            first_name = recipient.first_name.strip()
            greeting = f"Bonjour {first_name}" if first_name else "Bonjour"
            sender.send_email(
                to=recipient.email,
                subject=subject,
                body=(
                    f"{greeting},\n\n"
                    f"L’événement « {event.name} » a été reporté.\n\n"
                    f"{details}\n\n"
                    "Retrouvez les informations à jour dans « Mes billets » "
                    "sur FANID.\n\n"
                    "L’équipe FANID"
                ),
            )
            sent += 1
    except Exception as exc:
        _retry(self, exc)

    return {
        "sent": True,
        "recipients": sent,
    }
