from __future__ import annotations

import uuid
from typing import Any

from celery import shared_task

from .gateways import get_payment_gateway
from .services import PaymentRefundGatewayError, execute_payment_refund, request_event_refunds


@shared_task(
    bind=True,
    name="payments.event_cancellation_refunds",
    max_retries=5,
)
def process_cancelled_event_refunds(
    self: Any,
    *,
    event_id: str,
) -> dict[str, int | bool | str]:
    """Crée puis exécute les remboursements liés à une annulation."""

    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        return {"processed": False, "reason": "invalid_identifier"}

    refunds = request_event_refunds(event_id=event_uuid)
    gateway = get_payment_gateway()
    succeeded = 0
    pending = 0

    try:
        for refund in refunds:
            completed = execute_payment_refund(
                refund_id=refund.id,
                gateway=gateway,
            )
            if completed.status == "SUCCEEDED":
                succeeded += 1
            else:
                pending += 1
    except PaymentRefundGatewayError as exc:
        retries = int(getattr(self.request, "retries", 0))
        raise self.retry(
            exc=exc,
            countdown=min(30 * (2**retries), 600),
        ) from exc

    return {
        "processed": True,
        "refunds_succeeded": succeeded,
        "refunds_pending": pending,
    }
