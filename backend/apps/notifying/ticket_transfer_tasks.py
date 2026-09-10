from __future__ import annotations

import uuid

from celery import shared_task

from apps.core.adapters.notifications import build_notification_sender
from apps.ticketing.api import get_ticket_transfer_notification_summary


def _greeting(first_name: str) -> str:
    first_name = first_name.strip()
    return f"Bonjour {first_name}" if first_name else "Bonjour"


@shared_task(name="notifying.ticket_transfer_emails")
def send_ticket_transfer_emails(*, transfer_audit_id: str) -> dict:
    """Notify both Fans after a committed ticket transfer."""
    try:
        audit_id = uuid.UUID(transfer_audit_id)
    except (AttributeError, TypeError, ValueError):
        return {"sent": False, "reason": "invalid_identifier"}

    transfer = get_ticket_transfer_notification_summary(
        transfer_audit_id=audit_id,
    )
    if transfer is None:
        return {"sent": False, "reason": "transfer_missing"}

    notification_sender = build_notification_sender()

    notification_sender.send_email(
        to=transfer.previous_owner_email,
        subject=f"Billet transféré — {transfer.event_name}",
        body=(
            f"{_greeting(transfer.previous_owner_first_name)},\n\n"
            f"Votre billet pour « {transfer.event_name} » a été transféré à "
            f"{transfer.recipient_email}.\n\n"
            "Votre ancien QR dynamique est désormais invalide.\n\n"
            "L’équipe FANID"
        ),
    )
    notification_sender.send_email(
        to=transfer.recipient_email,
        subject=f"Vous avez reçu un billet — {transfer.event_name}",
        body=(
            f"{_greeting(transfer.recipient_first_name)},\n\n"
            f"{transfer.previous_owner_email} vous a transféré un billet pour "
            f"« {transfer.event_name} ».\n\n"
            "Le billet est disponible dans « Mes billets ». Utilisez son "
            "nouveau QR dynamique le jour de l’événement.\n\n"
            "L’équipe FANID"
        ),
    )
    return {"sent": True, "recipients": 2}
