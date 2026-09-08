from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from .models import TICKET_VOID, Ticket


@dataclass(frozen=True)
class TicketBuyerNotificationRecipient:
    user_id: UUID
    email: str
    first_name: str


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
