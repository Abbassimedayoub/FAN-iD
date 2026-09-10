from __future__ import annotations

from uuid import UUID

from django.db import transaction

from apps.core.exceptions import InvalidStateTransitionError
from apps.ordering.api import get_order_ticket_issuance_snapshot

from ..models import Ticket


@transaction.atomic
def issue_tickets_for_order(*, order_id: UUID) -> list[Ticket]:
    """
    Émet les billets d'une commande payée.

    La contrainte unique (order_line, sequence) rend cette opération idempotente :
    un webhook Stripe rejoué ne peut pas créer de billet supplémentaire.
    """
    order = get_order_ticket_issuance_snapshot(
        order_id=order_id,
    )
    if order is None:
        raise InvalidStateTransitionError(
            details={
                "order_id": str(order_id),
                "reason": "order_not_found",
            },
        )

    if not order.is_paid:
        raise InvalidStateTransitionError(
            details={
                "order_id": str(order.order_id),
                "status": order.status,
                "reason": "order_not_paid",
            },
        )

    issued: list[Ticket] = []

    for line in order.lines:
        for sequence in range(1, line.quantity + 1):
            ticket, _ = Ticket.objects.get_or_create(
                order_line_id=line.order_line_id,
                sequence=sequence,
                defaults={
                    "user_id": order.user_id,
                    "event_id": line.event_id,
                    "ticket_category_id": line.ticket_category_id,
                },
            )
            issued.append(ticket)

    return issued
