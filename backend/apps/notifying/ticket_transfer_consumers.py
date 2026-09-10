from __future__ import annotations

from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent
from apps.ticketing.events import TICKET_TRANSFERRED_EVENT

from .ticket_transfer_tasks import send_ticket_transfer_emails


class TicketTransferNotificationConsumer(BaseConsumer):
    """Schedule transfer emails after the Outbox transaction commits."""

    name = "notifying.ticket_transfer_notifications"
    handled_event_types = {TICKET_TRANSFERRED_EVENT}

    def handle(self, event: OutboxEvent) -> None:
        transfer_audit_id = str(event.aggregate_id)
        self.defer(
            lambda: send_ticket_transfer_emails.delay(
                transfer_audit_id=transfer_audit_id,
            )
        )
