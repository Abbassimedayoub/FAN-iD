from __future__ import annotations

from apps.catalog.events import CATALOG_EVENT_POSTPONED
from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent

from .event_buyer_tasks import send_event_buyer_postponement_emails


class EventBuyerNotificationConsumer(BaseConsumer):
    """Schedule buyer emails after an event is postponed."""

    name = "notifying.event_buyer_notifications"
    handled_event_types = {CATALOG_EVENT_POSTPONED}

    def handle(self, event: OutboxEvent) -> None:
        if event.payload.get("notify_buyers") is not True:
            return

        event_id = str(event.aggregate_id)
        self.defer(
            lambda: send_event_buyer_postponement_emails.delay(
                event_id=event_id,
            )
        )
