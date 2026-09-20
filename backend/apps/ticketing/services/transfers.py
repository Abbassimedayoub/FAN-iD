from __future__ import annotations

from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ConflictError, PermissionBusinessError, ValidationBusinessError
from apps.core.outbox.publisher import publish_event
from apps.identity.api import resolve_fan_user_id_by_email

from ..events import AGGREGATE_TICKET_TRANSFER, TICKET_TRANSFERRED_EVENT
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
    """Transfer a ticket atomically and invalidate its existing QR codes."""
    ticket = Ticket.objects.select_for_update().select_related("event").get(pk=ticket_id)

    if ticket.user_id != owner_user_id:
        raise TicketTransferForbiddenError()

    recipient_user_id = resolve_fan_user_id_by_email(
        email=recipient_email,
    )
    if recipient_user_id is None or recipient_user_id == ticket.user_id:
        raise TicketTransferRecipientError()

    moment = now or timezone.now()
    if (
        ticket.status != TICKET_VALID
        or ticket.event.status not in {ticket.event.PUBLISHED, ticket.event.POSTPONED}
        or moment >= _event_transfer_deadline(ticket)
    ):
        raise TicketTransferUnavailableError()

    previous_user_id = ticket.user_id
    ticket.user_id = recipient_user_id
    ticket.qr_version += 1
    ticket.save(update_fields=["user", "qr_version", "updated_at"])

    audit = TicketTransferAudit.objects.create(
        ticket=ticket,
        previous_user_id=previous_user_id,
        recipient_user_id=recipient_user_id,
    )

    publish_event(
        event_type=TICKET_TRANSFERRED_EVENT,
        aggregate_type=AGGREGATE_TICKET_TRANSFER,
        aggregate_id=audit.id,
        payload={},
        actor_id=owner_user_id,
    )
    return ticket
