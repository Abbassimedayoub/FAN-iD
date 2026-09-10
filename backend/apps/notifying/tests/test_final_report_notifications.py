from __future__ import annotations

import uuid
from types import SimpleNamespace

from apps.access.events import ACCESS_FINAL_REPORT_READY
from apps.notifying.final_report_consumers import FinalReportNotificationConsumer


def test_final_report_consumer_defers_email_task(monkeypatch):
    scheduled: list[dict[str, str]] = []
    consumer = FinalReportNotificationConsumer()
    event_id = uuid.uuid4()

    monkeypatch.setattr(
        "apps.notifying.final_report_consumers." "send_organizer_final_report_email.delay",
        lambda **kwargs: scheduled.append(kwargs),
    )
    monkeypatch.setattr(
        consumer,
        "defer",
        lambda callback: callback(),
    )

    assert ACCESS_FINAL_REPORT_READY in consumer.handled_event_types

    consumer.handle(
        SimpleNamespace(
            payload={
                "event_id": str(event_id),
            },
        )
    )

    assert scheduled == [
        {
            "event_id": str(event_id),
        }
    ]


def test_final_report_consumer_ignores_missing_event_id(monkeypatch):
    scheduled: list[dict[str, str]] = []
    consumer = FinalReportNotificationConsumer()

    monkeypatch.setattr(
        "apps.notifying.final_report_consumers." "send_organizer_final_report_email.delay",
        lambda **kwargs: scheduled.append(kwargs),
    )
    monkeypatch.setattr(
        consumer,
        "defer",
        lambda callback: callback(),
    )

    consumer.handle(
        SimpleNamespace(
            payload={},
        )
    )

    assert scheduled == []
