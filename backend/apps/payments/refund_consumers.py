from __future__ import annotations

from apps.catalog.events import CATALOG_EVENT_CANCELLED
from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent

from .refund_tasks import process_cancelled_event_refunds


class EventCancellationRefundConsumer(BaseConsumer):
    """Schedule refunds after an event is cancelled."""

    name = "payments.event_cancellation_refunds"
    handled_event_types = {CATALOG_EVENT_CANCELLED}

    def handle(self, event: OutboxEvent) -> None:
        if event.payload.get("refund_requested") is not True:
            return

        event_id = str(event.aggregate_id)
        self.defer(
            lambda: process_cancelled_event_refunds.delay(
                event_id=event_id,
            )
        )
