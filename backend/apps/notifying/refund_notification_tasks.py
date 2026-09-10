from __future__ import annotations

import uuid
from typing import Any

from celery import shared_task

from apps.core.adapters.notifications import build_notification_sender
from apps.payments.api import get_payment_refund_notification_summary


def _amount_label(amount_cents: int) -> str:
    return f"{amount_cents / 100:.2f}".replace(".", ",") + " €"


@shared_task(
    bind=True,
    name="notifying.payment_refund_succeeded_email",
    max_retries=5,
)
def send_refund_succeeded_email(
    self: Any,
    *,
    refund_id: str,
) -> dict[str, Any]:
    try:
        refund_uuid = uuid.UUID(refund_id)
    except ValueError:
        return {"sent": False, "reason": "invalid_identifier"}

    refund = get_payment_refund_notification_summary(
        refund_id=refund_uuid,
    )
    if refund is None:
        return {"sent": False, "reason": "refund_not_succeeded"}

    first_name = refund.buyer_first_name.strip()
    greeting = f"Bonjour {first_name}" if first_name else "Bonjour"

    try:
        build_notification_sender().send_email(
            to=refund.buyer_email,
            subject=f"[FANID] Remboursement effectué : {refund.event_name}",
            body=(
                f"{greeting},\n\n"
                f"L’événement « {refund.event_name} » a été annulé.\n\n"
                f"Votre remboursement de {_amount_label(refund.amount_cents)} "
                "a été effectué par Stripe. Les billets concernés ne sont "
                "désormais plus utilisables.\n\n"
                "L’équipe FANID"
            ),
        )
    except Exception as exc:
        retries = int(getattr(self.request, "retries", 0))
        raise self.retry(
            exc=exc,
            countdown=min(30 * (2**retries), 600),
        ) from exc

    return {"sent": True, "refund_id": str(refund.id)}
