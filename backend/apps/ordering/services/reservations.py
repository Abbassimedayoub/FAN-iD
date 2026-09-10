from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable, cast
from uuid import UUID

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.catalog.lifecycle import EventLifecycleLike, event_sales_open
from apps.catalog.models import TicketCategory
from apps.core.exceptions import ConflictError, NotFoundBusinessError, ValidationBusinessError
from apps.ordering.models import Order, OrderLine, StockHold, StockHoldLine

HOLD_TTL = timedelta(minutes=10)


class InvalidReservationError(ValidationBusinessError):
    default_code = "INVALID_RESERVATION"


class StockUnavailableError(ConflictError):
    default_code = "STOCK_UNAVAILABLE"
    default_message = "Le stock demandé n’est plus disponible."


class SaleUnavailableError(ConflictError):
    default_code = "SALE_UNAVAILABLE"
    default_message = "La vente de cet événement n’est pas ouverte."


@dataclass(frozen=True)
class ReservationLine:
    ticket_category_id: UUID
    quantity: int


@transaction.atomic
def reserve_stock(*, user, lines: Iterable[ReservationLine], now=None) -> Order:
    moment = now or timezone.now()
    requested: dict[UUID, int] = {}

    for line in lines:
        if line.quantity <= 0:
            raise InvalidReservationError(
                details={"reason": "quantity doit être strictement positive."},
            )
        requested[line.ticket_category_id] = requested.get(line.ticket_category_id, 0) + line.quantity

    if not requested:
        raise InvalidReservationError(
            details={"reason": "Au moins une ligne est requise."},
        )

    requested_categories = list(
        TicketCategory.objects.select_related("event")
        .filter(pk__in=requested)
        .values_list("event_id", flat=True)
    )

    if len(requested_categories) != len(requested):
        raise NotFoundBusinessError(code="TICKET_CATEGORY_NOT_FOUND")

    locked_categories = list(
        TicketCategory.objects.select_for_update()
        .select_related("event")
        .filter(event_id__in=set(requested_categories))
        .order_by("pk")
    )
    categories = {category.id: category for category in locked_categories}

    held_rows = (
        StockHoldLine.objects.filter(
            ticket_category_id__in=categories,
            stock_hold__consumed=False,
            stock_hold__expires_at__gt=moment,
        )
        .values("ticket_category_id")
        .annotate(quantity=Sum("quantity"))
    )
    held = {row["ticket_category_id"]: row["quantity"] for row in held_rows}

    for category_id, quantity in requested.items():
        category = categories[category_id]
        if not event_sales_open(cast(EventLifecycleLike, category.event), at=moment):
            raise SaleUnavailableError(details={"event_id": str(category.event_id)})

        available = category.quota - category.sold_count - held.get(category_id, 0)
        if quantity > available:
            raise StockUnavailableError(
                details={
                    "ticket_category_id": str(category_id),
                    "requested": quantity,
                    "available": max(available, 0),
                },
            )

    for event_id in {category.event_id for category in locked_categories}:
        event_categories = [category for category in locked_categories if category.event_id == event_id]
        capacity = event_categories[0].event.capacity_total
        if capacity is None:
            continue

        occupied = sum(category.sold_count + held.get(category.id, 0) for category in event_categories)
        requested_for_event = sum(
            quantity
            for category_id, quantity in requested.items()
            if categories[category_id].event_id == event_id
        )
        if occupied + requested_for_event > capacity:
            raise StockUnavailableError(
                details={"event_id": str(event_id), "requested": requested_for_event},
            )

    total = sum(
        categories[category_id].unit_price_cents * quantity for category_id, quantity in requested.items()
    )
    order = Order.objects.create(user=user, total_amount_cents=total)
    hold = StockHold.objects.create(order=order, expires_at=moment + HOLD_TTL)

    for category_id, quantity in requested.items():
        category = categories[category_id]
        OrderLine.objects.create(
            order=order,
            ticket_category=category,
            label=category.name,
            quantity=quantity,
            unit_price_cents=category.unit_price_cents,
        )
        StockHoldLine.objects.create(
            stock_hold=hold,
            ticket_category=category,
            quantity=quantity,
        )

    return order
