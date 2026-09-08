from __future__ import annotations

from celery import shared_task

from apps.core.adapters.notifications import build_notification_sender
from apps.ticketing.models import TicketTransferAudit


def _greeting(first_name: str) -> str:
    first_name = first_name.strip()
    return f"Bonjour {first_name}" if first_name else "Bonjour"


@shared_task(name="notifying.ticket_transfer_emails")
def send_ticket_transfer_emails(*, transfer_audit_id: str) -> dict:
    """Informe les deux Fans après un transfert de billet confirmé."""
    audit = (
        TicketTransferAudit.objects.select_related(
            "ticket__event",
            "previous_user",
            "recipient_user",
        )
        .filter(pk=transfer_audit_id)
        .first()
    )
    if audit is None:
        return {"sent": False, "reason": "transfer_missing"}

    event = audit.ticket.event
    notification_sender = build_notification_sender()
    previous_owner = audit.previous_user
    recipient = audit.recipient_user

    notification_sender.send_email(
        to=previous_owner.email,
        subject=f"Billet transféré — {event.name}",
        body=(
            f"{_greeting(previous_owner.first_name)},\n\n"
            f"Votre billet pour « {event.name} » a été transféré à "
            f"{recipient.email}.\n\n"
            "Votre ancien QR dynamique est désormais invalide.\n\n"
            "L’équipe FANID"
        ),
    )
    notification_sender.send_email(
        to=recipient.email,
        subject=f"Vous avez reçu un billet — {event.name}",
        body=(
            f"{_greeting(recipient.first_name)},\n\n"
            f"{previous_owner.email} vous a transféré un billet pour "
            f"« {event.name} ».\n\n"
            "Le billet est disponible dans « Mes billets ». Utilisez son "
            "nouveau QR dynamique le jour de l’événement.\n\n"
            "L’équipe FANID"
        ),
    )
    return {"sent": True, "recipients": 2}
