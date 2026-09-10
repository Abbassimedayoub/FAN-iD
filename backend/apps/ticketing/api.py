from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt
from django.conf import settings

from .models import TICKET_USED, TICKET_VALID, TICKET_VOID, Ticket, TicketTransferAudit
from .services.qr import QR_ISSUER, QR_TYPE


@dataclass(frozen=True)
class TicketBuyerNotificationRecipient:
    user_id: UUID
    email: str
    first_name: str


@dataclass(frozen=True)
class TicketTransferNotificationSummary:
    """Public notification data for a completed ticket transfer."""

    previous_owner_email: str
    previous_owner_first_name: str
    recipient_email: str
    recipient_first_name: str
    event_name: str


def list_ticket_buyer_notification_recipients(
    *,
    event_id: UUID,
) -> list[TicketBuyerNotificationRecipient]:
    """Acheteurs uniques de billets payés et non annulés d'un événement."""
    recipients: list[TicketBuyerNotificationRecipient] = []
    seen_user_ids: set[UUID] = set()

    tickets = (
        Ticket.objects.filter(event_id=event_id)
        .exclude(status=TICKET_VOID)
        .select_related("user")
        .order_by("user_id", "created_at")
    )

    for ticket in tickets:
        user = ticket.user
        if user.id in seen_user_ids:
            continue
        seen_user_ids.add(user.id)
        recipients.append(
            TicketBuyerNotificationRecipient(
                user_id=user.id,
                email=user.email,
                first_name=user.first_name,
            )
        )

    return recipients


def get_ticket_transfer_notification_summary(
    *,
    transfer_audit_id: UUID,
) -> TicketTransferNotificationSummary | None:
    """Return notification data for a completed ticket transfer."""
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
        return None

    return TicketTransferNotificationSummary(
        previous_owner_email=audit.previous_user.email,
        previous_owner_first_name=audit.previous_user.first_name,
        recipient_email=audit.recipient_user.email,
        recipient_first_name=audit.recipient_user.first_name,
        event_name=audit.ticket.event.name,
    )


@dataclass(frozen=True, slots=True)
class TicketAdmissionSnapshot:
    """Minimal ticket state required by the access admission workflow."""

    id: UUID
    event_id: UUID
    qr_version: int
    is_valid: bool
    is_used: bool


def parse_ticket_qr_identity(
    *,
    token: str,
) -> tuple[UUID, int] | None:
    """Return the ticket identity encoded in a valid FANID ticket QR."""
    try:
        claims = jwt.decode(
            token,
            settings.QR_SIGNING_KEY,
            algorithms=["HS256"],
            issuer=QR_ISSUER,
        )
        if claims.get("typ") != QR_TYPE:
            return None

        return UUID(str(claims["tid"])), int(claims["qv"])
    except (
        jwt.InvalidTokenError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return None


def lock_ticket_for_admission(
    *,
    ticket_id: UUID,
) -> TicketAdmissionSnapshot | None:
    """Lock and return the ticket state needed by an admission transaction."""
    ticket = Ticket.objects.select_for_update().filter(pk=ticket_id).first()
    if ticket is None:
        return None

    return TicketAdmissionSnapshot(
        id=ticket.id,
        event_id=ticket.event_id,
        qr_version=ticket.qr_version,
        is_valid=ticket.status == TICKET_VALID,
        is_used=ticket.status == TICKET_USED,
    )


def mark_ticket_used(
    *,
    ticket_id: UUID,
) -> None:
    """Mark a ticket as used inside the caller's admission transaction."""
    Ticket.objects.filter(pk=ticket_id).update(
        status=TICKET_USED,
    )


def count_active_tickets_for_event(
    *,
    event_id: UUID,
) -> int:
    """Return the number of non-void tickets for an event."""
    return Ticket.objects.filter(event_id=event_id).exclude(status=TICKET_VOID).count()


@dataclass(frozen=True, slots=True)
class EventTicketStatusCounts:
    """Ticket status counts required by event reporting."""

    total_count: int
    used_count: int
    voided_count: int


def get_event_ticket_status_counts(
    *,
    event_id: UUID,
) -> EventTicketStatusCounts:
    """Return total, used and voided ticket counts for an event."""
    tickets = Ticket.objects.filter(
        event_id=event_id,
    )

    return EventTicketStatusCounts(
        total_count=tickets.count(),
        used_count=tickets.filter(
            status=TICKET_USED,
        ).count(),
        voided_count=tickets.filter(
            status=TICKET_VOID,
        ).count(),
    )


def issue_tickets_for_order(
    *,
    order_id: UUID,
) -> None:
    """Issue tickets for a confirmed order through ticketing."""
    from .services.issuance import issue_tickets_for_order as _issue_tickets_for_order

    _issue_tickets_for_order(
        order_id=order_id,
    )


def void_valid_tickets_for_order_event(
    *,
    event_id: UUID,
    order_id: UUID,
) -> int:
    """Void valid tickets for one order and event."""
    return Ticket.objects.filter(
        event_id=event_id,
        order_line__order_id=order_id,
        status=TICKET_VALID,
    ).update(
        status=TICKET_VOID,
    )
