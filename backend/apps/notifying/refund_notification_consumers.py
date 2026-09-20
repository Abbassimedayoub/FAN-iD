from __future__ import annotations

from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent
from apps.payments.events import PAYMENT_REFUND_SUCCEEDED

from .refund_notification_tasks import send_refund_succeeded_email


class PaymentRefundNotificationConsumer(BaseConsumer):
    """Schedule the email only after the refund is confirmed."""

    name = "notifying.payment_refund_succeeded_email"
    handled_event_types = {PAYMENT_REFUND_SUCCEEDED}

    def handle(self, event: OutboxEvent) -> None:
        refund_id = str(event.aggregate_id)
        self.defer(
            lambda: send_refund_succeeded_email.delay(
                refund_id=refund_id,
            )
        )
