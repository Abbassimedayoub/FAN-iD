from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.access.completion_consumers import EventCompletionAdmissionConsumer
from apps.access.models import EventAdmissionSession
from apps.catalog.models import Category, Event
from apps.catalog.services.completion import complete_elapsed_events
from apps.core.outbox.relay import relay_batch


@pytest.mark.django_db
def test_completion_consumer_closes_open_admission_automatically(
    django_user_model,
    roles,
):
    now = timezone.now()
    owner = django_user_model.objects.create_user(
        email="completion-owner@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=now,
        role=roles["FAN"],
    )
    category = Category.objects.create(name="Admission completion category")
    event = Event.objects.create(
        category=category,
        name="Admission completion event",
        status=Event.COMPLETED,
        starts_at=now - datetime.timedelta(hours=3),
        ends_at=now - datetime.timedelta(minutes=1),
    )
    session = EventAdmissionSession.objects.create(
        event=event,
        opened_at=now - datetime.timedelta(hours=2),
        scheduled_starts_at=event.starts_at,
        opened_by=owner,
    )

    EventCompletionAdmissionConsumer().handle(
        SimpleNamespace(aggregate_id=event.id),
    )

    session.refresh_from_db()
    assert session.closed_at is not None
    assert session.closed_by_id is None
    assert session.closed_automatically is True


@pytest.mark.django_db
def test_elapsed_event_closes_admission_through_outbox(
    django_user_model,
    roles,
):
    now = timezone.now()
    owner = django_user_model.objects.create_user(
        email="completion-outbox-owner@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=now,
        role=roles["FAN"],
    )
    category = Category.objects.create(name="Admission outbox category")
    event = Event.objects.create(
        category=category,
        name="Admission outbox event",
        status=Event.PUBLISHED,
        starts_at=now - datetime.timedelta(hours=3),
        ends_at=now - datetime.timedelta(minutes=1),
    )
    session = EventAdmissionSession.objects.create(
        event=event,
        opened_at=now - datetime.timedelta(hours=2),
        scheduled_starts_at=event.starts_at,
        opened_by=owner,
    )

    assert complete_elapsed_events(now=now) == 1
    assert relay_batch().published >= 1

    event.refresh_from_db()
    session.refresh_from_db()

    assert event.status == Event.COMPLETED
    assert session.closed_at is not None
    assert session.closed_by_id is None
    assert session.closed_automatically is True
