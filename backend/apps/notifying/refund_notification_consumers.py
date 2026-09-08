from __future__ import annotations

from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent
from apps.payments.events import PAYMENT_REFUND_SUCCEEDED

from .refund_notification_tasks import send_refund_succeeded_email


class PaymentRefundNotificationConsumer(BaseConsumer):
    """Planifie l'e-mail uniquement après remboursement confirmé."""

    name = "notifying.payment_refund_succeeded_email"
    handled_event_types = {PAYMENT_REFUND_SUCCEEDED}

    def handle(self, event: OutboxEvent) -> None:
        refund_id = str(event.aggregate_id)
        self.defer(
            lambda: send_refund_succeeded_email.delay(
                refund_id=refund_id,
            )
        )
