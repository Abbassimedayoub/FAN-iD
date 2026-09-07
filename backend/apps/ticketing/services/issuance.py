from __future__ import annotations

from django.db import transaction

from apps.core.exceptions import InvalidStateTransitionError
from apps.ordering.models import ORDER_PAID, Order

from ..models import Ticket


@transaction.atomic
def issue_tickets_for_order(*, order: Order) -> list[Ticket]:
    """
    Émet les billets d'une commande payée.

    La contrainte unique (order_line, sequence) rend cette opération idempotente :
    un webhook Stripe rejoué ne peut pas créer de billet supplémentaire.
    """
    if order.status != ORDER_PAID:
        raise InvalidStateTransitionError(
            details={
                "order_id": str(order.id),
                "status": order.status,
                "reason": "order_not_paid",
            },
        )

    issued: list[Ticket] = []

    lines = (
        order.lines.select_related("ticket_category__event")
        .order_by("created_at", "id")
    )

    for line in lines:
        ticket_category = line.ticket_category

        for sequence in range(1, line.quantity + 1):
            ticket, _ = Ticket.objects.get_or_create(
                order_line=line,
                sequence=sequence,
                defaults={
                    "user": order.user,
                    "event": ticket_category.event,
                    "ticket_category": ticket_category,
                },
            )
            issued.append(ticket)

    return issued
