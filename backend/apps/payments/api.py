"""Public read interface for the payments context."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.db.models import Sum

from .models import PAYMENT_REFUND_SUCCEEDED, PaymentRefund


@dataclass(
    frozen=True,
    slots=True,
)
class PaymentRefundNotificationSummary:
    """Minimal data required to notify a buyer about a successful refund."""

    id: uuid.UUID
    buyer_email: str
    buyer_first_name: str
    event_name: str
    amount_cents: int


def get_payment_refund_notification_summary(
    *,
    refund_id: uuid.UUID,
) -> PaymentRefundNotificationSummary | None:
    """Return notification data only for a successful refund."""
    refund = (
        PaymentRefund.objects.select_related(
            "event",
            "payment_intent__order__user",
        )
        .filter(
            pk=refund_id,
            status=PAYMENT_REFUND_SUCCEEDED,
        )
        .first()
    )

    if refund is None:
        return None

    buyer = refund.payment_intent.order.user

    return PaymentRefundNotificationSummary(
        id=refund.pk,
        buyer_email=buyer.email,
        buyer_first_name=buyer.first_name,
        event_name=refund.event.name,
        amount_cents=refund.amount_cents,
    )


def get_succeeded_refunds_total_cents(
    *,
    event_id: uuid.UUID,
) -> int:
    """Return the total amount of successful refunds for an event."""
    total = PaymentRefund.objects.filter(
        event_id=event_id,
        status=PAYMENT_REFUND_SUCCEEDED,
    ).aggregate(
        total=Sum("amount_cents"),
    )["total"]

    return int(total or 0)
