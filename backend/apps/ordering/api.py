"""Public read interface for the ordering context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.db.models import F, Sum

from apps.core.exceptions import ConflictError

from .models import ORDER_PAID, ORDER_PENDING, Order, OrderLine, StockHold


def get_paid_event_gross_revenue_cents(
    *,
    event_id: UUID,
) -> int:
    """Return gross revenue from paid order lines for an event."""
    total = OrderLine.objects.filter(
        order__status=ORDER_PAID,
        ticket_category__event_id=event_id,
    ).aggregate(
        total=Sum(
            F("quantity") * F("unit_price_cents"),
        ),
    )["total"]

    return int(total or 0)


class ReservationExpiredError(ConflictError):
    default_code = "RESERVATION_EXPIRED"
    default_message = "La réservation a expiré."


@dataclass(frozen=True, slots=True)
class OrderPaymentHoldSnapshot:
    """Locked stock hold state required by the payment workflow."""

    consumed: bool
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class OrderPaymentIntentSnapshot:
    """Locked order state required before creating a payment intent."""

    id: UUID
    status: str
    total_amount_cents: int
    is_paid: bool
    is_pending: bool
    hold: OrderPaymentHoldSnapshot | None


def lock_order_for_payment_intent(
    *,
    order_id: UUID,
    user_id: UUID,
) -> OrderPaymentIntentSnapshot | None:
    """Lock and return the order state required by payments."""
    order = (
        Order.objects.select_for_update()
        .filter(
            pk=order_id,
            user_id=user_id,
        )
        .first()
    )
    if order is None:
        return None

    hold = StockHold.objects.select_for_update().filter(order_id=order.id).first()

    hold_snapshot = None
    if hold is not None:
        hold_snapshot = OrderPaymentHoldSnapshot(
            consumed=hold.consumed,
            expires_at=hold.expires_at,
        )

    return OrderPaymentIntentSnapshot(
        id=order.id,
        status=order.status,
        total_amount_cents=order.total_amount_cents,
        is_paid=order.status == ORDER_PAID,
        is_pending=order.status == ORDER_PENDING,
        hold=hold_snapshot,
    )


def confirm_order_payment(
    *,
    order_id: UUID,
    now: datetime | None = None,
) -> None:
    """Confirm an order through the ordering context public boundary."""
    from .services.confirmation import confirm_order_payment as _confirm_order_payment

    _confirm_order_payment(
        order_id=order_id,
        now=now,
    )


def list_paid_order_ids_for_event(
    *,
    event_id: UUID,
) -> tuple[UUID, ...]:
    """Return paid order IDs containing lines for an event."""
    return tuple(
        Order.objects.filter(
            status=ORDER_PAID,
            lines__ticket_category__event_id=event_id,
        )
        .values_list("id", flat=True)
        .distinct()
    )


def get_order_event_amount_cents(
    *,
    order_id: UUID,
    event_id: UUID,
) -> int:
    """Return the immutable order-line amount associated with an event."""
    total = OrderLine.objects.filter(
        order_id=order_id,
        ticket_category__event_id=event_id,
    ).aggregate(
        total=Sum(
            F("quantity") * F("unit_price_cents"),
        ),
    )["total"]

    return int(total or 0)


@dataclass(frozen=True, slots=True)
class OrderTicketIssuanceLine:
    """One immutable order line required for ticket issuance."""

    order_line_id: UUID
    ticket_category_id: UUID
    event_id: UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class OrderTicketIssuanceSnapshot:
    """Ordering data required by ticketing to issue tickets."""

    order_id: UUID
    user_id: UUID
    status: str
    is_paid: bool
    lines: tuple[OrderTicketIssuanceLine, ...]


def get_order_ticket_issuance_snapshot(
    *,
    order_id: UUID,
) -> OrderTicketIssuanceSnapshot | None:
    """Return immutable paid-order data required by ticketing."""
    order = Order.objects.filter(
        pk=order_id,
    ).first()
    if order is None:
        return None

    line_rows = (
        OrderLine.objects.filter(
            order_id=order_id,
        )
        .values_list(
            "id",
            "ticket_category_id",
            "ticket_category__event_id",
            "quantity",
        )
        .order_by(
            "created_at",
            "id",
        )
    )

    lines = tuple(
        OrderTicketIssuanceLine(
            order_line_id=order_line_id,
            ticket_category_id=ticket_category_id,
            event_id=event_id,
            quantity=quantity,
        )
        for (
            order_line_id,
            ticket_category_id,
            event_id,
            quantity,
        ) in line_rows
    )

    return OrderTicketIssuanceSnapshot(
        order_id=order.id,
        user_id=order.user_id,
        status=order.status,
        is_paid=order.status == ORDER_PAID,
        lines=lines,
    )
