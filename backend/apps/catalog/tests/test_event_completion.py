from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.catalog.events import CATALOG_EVENT_COMPLETED
from apps.catalog.models import Category, Event
from apps.catalog.services.completion import complete_elapsed_events
from apps.core.outbox.models import OutboxEvent


@pytest.mark.django_db
def test_elapsed_event_is_completed_once_and_publishes_outbox():
    now = timezone.now()
    category = Category.objects.create(name="Completion category")
    event = Event.objects.create(
        category=category,
        name="Completion event",
        status=Event.PUBLISHED,
        starts_at=now - datetime.timedelta(hours=3),
        ends_at=now - datetime.timedelta(minutes=1),
    )

    assert complete_elapsed_events(now=now) == 1

    event.refresh_from_db()
    assert event.status == Event.COMPLETED

    outbox = OutboxEvent.objects.get(
        event_type=CATALOG_EVENT_COMPLETED,
        aggregate_id=event.id,
    )
    assert outbox.payload["status"] == Event.COMPLETED
    assert outbox.payload["notify_buyers"] is False

    assert complete_elapsed_events(now=now) == 0
    assert (
        OutboxEvent.objects.filter(
            event_type=CATALOG_EVENT_COMPLETED,
            aggregate_id=event.id,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_event_ending_after_midnight_completes_after_its_real_end():
    category = Category.objects.create(name="Completion midnight category")
    start = datetime.datetime(2026, 9, 8, 22, 0, tzinfo=datetime.UTC)
    end = datetime.datetime(2026, 9, 9, 1, 0, tzinfo=datetime.UTC)
    event = Event.objects.create(
        category=category,
        name="Completion after midnight",
        status=Event.PUBLISHED,
        starts_at=start,
        ends_at=end,
    )

    assert (
        complete_elapsed_events(
            now=datetime.datetime(2026, 9, 9, 0, 59, tzinfo=datetime.UTC),
        )
        == 0
    )

    event.refresh_from_db()
    assert event.status == Event.PUBLISHED

    assert (
        complete_elapsed_events(
            now=datetime.datetime(2026, 9, 9, 1, 1, tzinfo=datetime.UTC),
        )
        == 1
    )

    event.refresh_from_db()
    assert event.status == Event.COMPLETED
