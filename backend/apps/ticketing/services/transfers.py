from __future__ import annotations

from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ConflictError, PermissionBusinessError, ValidationBusinessError
from apps.identity.constants import ROLE_FAN
from apps.identity.models import User

from ..models import TICKET_VALID, Ticket, TicketTransferAudit


class TicketTransferUnavailableError(ConflictError):
    default_code = "TICKET_TRANSFER_UNAVAILABLE"
    default_message = "Ce billet ne peut pas être transféré."


class TicketTransferRecipientError(ValidationBusinessError):
    default_code = "TICKET_TRANSFER_RECIPIENT_INVALID"
    default_message = "Le destinataire doit être un Fan FANID existant."


class TicketTransferForbiddenError(PermissionBusinessError):
    default_code = "TICKET_TRANSFER_FORBIDDEN"
    default_message = "Vous ne pouvez transférer que vos propres billets."


def _event_transfer_deadline(ticket: Ticket) -> datetime:
    return ticket.event.postponed_to_starts_at or ticket.event.starts_at


@transaction.atomic
def transfer_ticket(
    *,
    ticket_id: UUID,
    owner_user_id: UUID,
    recipient_email: str,
    now: datetime | None = None,
) -> Ticket:
    """Transfère un billet de manière atomique et invalide ses QR existants."""
    ticket = (
        Ticket.objects.select_for_update()
        .select_related("event")
        .get(pk=ticket_id)
    )

    if ticket.user_id != owner_user_id:
        raise TicketTransferForbiddenError()

    recipient = (
        User.objects.select_related("role")
        .filter(
            email__iexact=recipient_email.strip(),
            role__name=ROLE_FAN,
            anonymized_at__isnull=True,
        )
        .first()
    )
    if recipient is None or recipient.pk == ticket.user_id:
        raise TicketTransferRecipientError()

    moment = now or timezone.now()
    if (
        ticket.status != TICKET_VALID
        or ticket.event.status not in {ticket.event.PUBLISHED, ticket.event.POSTPONED}
        or moment >= _event_transfer_deadline(ticket)
    ):
        raise TicketTransferUnavailableError()

    previous_user_id = ticket.user_id
    ticket.user_id = recipient.id
    ticket.qr_version += 1
    ticket.save(update_fields=["user", "qr_version", "updated_at"])

    audit = TicketTransferAudit.objects.create(
        ticket=ticket,
        previous_user_id=previous_user_id,
        recipient_user=recipient,
    )

    # L'e-mail ne part qu'après la validation définitive de la transaction.
    from apps.notifying.ticket_transfer_tasks import (
        send_ticket_transfer_emails,
    )

    audit_id = str(audit.id)
    transaction.on_commit(
        lambda: send_ticket_transfer_emails.delay(
            transfer_audit_id=audit_id,
        )
    )
    return ticket
