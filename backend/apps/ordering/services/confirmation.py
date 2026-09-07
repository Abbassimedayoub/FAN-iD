from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import TicketCategory
from apps.core.exceptions import (
    ConflictError,
    InvalidStateTransitionError,
    NotFoundBusinessError,
)
from apps.ordering.models import ORDER_PAID, ORDER_PENDING, Order, StockHold, StockHoldLine

from .reservations import StockUnavailableError


class ReservationExpiredError(ConflictError):
    default_code = "RESERVATION_EXPIRED"
    default_message = "La réservation a expiré."


@transaction.atomic
def confirm_order_payment(*, order_id: UUID, now=None) -> Order:
    """
    Finalise une commande après vérification réussie par une passerelle de paiement.

    Cette fonction est volontairement interne : un futur webhook de paiement
    devra vérifier la signature avant de l'appeler.
    """
    moment = now or timezone.now()

    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist as exc:
        raise NotFoundBusinessError(code="ORDER_NOT_FOUND") from exc

    if order.status == ORDER_PAID:
        return order

    if order.status != ORDER_PENDING:
        raise InvalidStateTransitionError(
            details={
                "order_id": str(order.id),
                "status": order.status,
                "target_status": ORDER_PAID,
            },
        )

    try:
        hold = StockHold.objects.select_for_update().get(order=order)
    except StockHold.DoesNotExist as exc:
        raise InvalidStateTransitionError(
            details={"order_id": str(order.id), "reason": "stock_hold_missing"},
        ) from exc

    if hold.consumed:
        raise InvalidStateTransitionError(
            details={"order_id": str(order.id), "reason": "stock_hold_consumed"},
        )

    if hold.expires_at <= moment:
        raise ReservationExpiredError(details={"order_id": str(order.id)})

    hold_lines = list(
        StockHoldLine.objects.filter(stock_hold=hold).values_list(
            "ticket_category_id",
            "quantity",
        )
    )
    quantities = defaultdict(int)
    for ticket_category_id, quantity in hold_lines:
        quantities[ticket_category_id] += quantity

    categories = {
        category.id: category
        for category in TicketCategory.objects.select_for_update()
        .filter(pk__in=quantities)
        .order_by("pk")
    }

    if len(categories) != len(quantities):
        raise InvalidStateTransitionError(
            details={"order_id": str(order.id), "reason": "ticket_category_missing"},
        )

    for ticket_category_id, quantity in quantities.items():
        category = categories[ticket_category_id]
        if category.sold_count + quantity > category.quota:
            raise StockUnavailableError(
                details={
                    "ticket_category_id": str(ticket_category_id),
                    "requested": quantity,
                    "available": max(category.quota - category.sold_count, 0),
                },
            )

    for ticket_category_id, quantity in quantities.items():
        category = categories[ticket_category_id]
        category.sold_count += quantity
        category.save(update_fields=["sold_count"])

    hold.consumed = True
    hold.save(update_fields=["consumed"])

    order.status = ORDER_PAID
    order.save(update_fields=["status"])

    # Import local : ordering confirme le paiement, ticketing émet les billets.
    # La transaction commune annule aussi la vente si l'émission échoue.
    from apps.ticketing.services import issue_tickets_for_order

    issue_tickets_for_order(order=order)

    return order
