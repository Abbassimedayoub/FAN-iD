from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import TicketCategory
from apps.core.exceptions import InvalidStateTransitionError, NotFoundBusinessError
from apps.ordering.api import ReservationExpiredError
from apps.ordering.models import ORDER_PAID, ORDER_PENDING, Order, StockHold, StockHoldLine

from .reservations import StockUnavailableError


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
    quantities: defaultdict[UUID, int] = defaultdict(int)
    for ticket_category_id, quantity in hold_lines:
        quantities[ticket_category_id] += quantity

    categories = {
        category.id: category
        for category in TicketCategory.objects.select_for_update().filter(pk__in=quantities).order_by("pk")
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

    # Keep ticket issuance inside the same transaction so any issuance
    # failure rolls the order confirmation back as well.
    from apps.ticketing.api import issue_tickets_for_order

    issue_tickets_for_order(
        order_id=order.id,
    )

    return order
