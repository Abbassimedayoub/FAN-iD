from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel, VersionedModel

ORDER_PENDING = "PENDING"
ORDER_PAID = "PAID"
ORDER_FAILED = "FAILED"
ORDER_EXPIRED = "EXPIRED"

ORDER_STATUSES = (
    ORDER_PENDING,
    ORDER_PAID,
    ORDER_FAILED,
    ORDER_EXPIRED,
)


class Order(UUIDModel, TimeStampedModel, VersionedModel):
    """User order with monetary amounts snapshotted in cents."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    status = models.CharField(
        max_length=20,
        default=ORDER_PENDING,
        choices=[(x, x) for x in ORDER_STATUSES],
    )

    total_amount_cents = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "ordering_order"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=list(ORDER_STATUSES)),
                name="ck_order_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "created_at"],
                name="ix_order_user_created",
            ),
            models.Index(
                fields=["status"],
                name="ix_order_status",
            ),
        ]


class OrderLine(UUIDModel, TimeStampedModel):
    """Order line with a snapshotted price."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    ticket_category = models.ForeignKey(
        "catalog.TicketCategory",
        on_delete=models.PROTECT,
        related_name="order_lines",
    )

    label = models.CharField(max_length=200)

    quantity = models.PositiveIntegerField(default=1)

    unit_price_cents = models.PositiveIntegerField()

    class Meta:
        db_table = "ordering_order_line"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="ck_order_line_quantity_positive",
            ),
        ]


class StockHold(UUIDModel, TimeStampedModel):
    """Temporary reservation held before payment."""

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="stock_hold",
    )

    expires_at = models.DateTimeField()

    consumed = models.BooleanField(default=False)

    class Meta:
        db_table = "ordering_stock_hold"
        indexes = [
            models.Index(
                fields=["expires_at"],
                name="ix_stock_hold_expiry",
            ),
        ]


class StockHoldLine(UUIDModel, TimeStampedModel):
    """
    Quantity reserved for one ticket category in a temporary hold; final inventory remains in
    TicketCategory.sold_count.
    """

    stock_hold = models.ForeignKey(
        StockHold,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    ticket_category = models.ForeignKey(
        "catalog.TicketCategory",
        on_delete=models.PROTECT,
        related_name="stock_hold_lines",
    )

    quantity = models.PositiveIntegerField()

    class Meta:
        db_table = "ordering_stock_hold_line"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="ck_stock_hold_line_quantity_positive",
            ),
            models.UniqueConstraint(
                fields=[
                    "stock_hold",
                    "ticket_category",
                ],
                name="uq_stock_hold_line_hold_ticket",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "ticket_category",
                    "stock_hold",
                ],
                name="ix_hold_line_ticket_hold",
            ),
        ]
