from __future__ import annotations

import uuid
from types import SimpleNamespace

from apps.notifying.ticket_transfer_consumers import TicketTransferNotificationConsumer
from apps.ticketing.events import TICKET_TRANSFERRED_EVENT


def test_ticket_transfer_consumer_defers_email_task(monkeypatch):
    scheduled: list[dict[str, str]] = []
    consumer = TicketTransferNotificationConsumer()
    transfer_audit_id = uuid.uuid4()

    monkeypatch.setattr(
        "apps.notifying.ticket_transfer_consumers." "send_ticket_transfer_emails.delay",
        lambda **kwargs: scheduled.append(kwargs),
    )
    monkeypatch.setattr(
        consumer,
        "defer",
        lambda callback: callback(),
    )

    assert TICKET_TRANSFERRED_EVENT in consumer.handled_event_types

    consumer.handle(
        SimpleNamespace(
            aggregate_id=transfer_audit_id,
        )
    )

    assert scheduled == [
        {
            "transfer_audit_id": str(transfer_audit_id),
        }
    ]
