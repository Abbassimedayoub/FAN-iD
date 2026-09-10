from __future__ import annotations

from apps.access.events import ACCESS_FINAL_REPORT_READY
from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent

from .final_report_tasks import send_organizer_final_report_email


class FinalReportNotificationConsumer(BaseConsumer):
    """Schedule final-report delivery after the Outbox transaction commits."""

    name = "notifying.final_report_email"
    handled_event_types = {ACCESS_FINAL_REPORT_READY}

    def handle(self, event: OutboxEvent) -> None:
        event_id = event.payload.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            return

        self.defer(
            lambda: send_organizer_final_report_email.delay(
                event_id=event_id,
            )
        )
