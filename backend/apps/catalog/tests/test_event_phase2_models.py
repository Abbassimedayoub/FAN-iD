from __future__ import annotations

import datetime

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.catalog.models import (
    Category,
    Event,
    TicketCategory,
)


@pytest.fixture
def event(db) -> Event:
    category = Category.objects.create(
        name="Concert Phase 2",
    )

    start = timezone.now() + datetime.timedelta(days=7)

    return Event.objects.create(
        category=category,
        name="Concert FANID Phase 2",
        starts_at=start,
        ends_at=start + datetime.timedelta(hours=3),
        venue="Stade Vélodrome, Marseille",
        capacity_total=12000,
    )


@pytest.mark.django_db
def test_event_accepts_org07_operational_fields(event):
    assert event.venue == "Stade Vélodrome, Marseille"
    assert event.capacity_total == 12000
    assert event.image_key == ""
    assert event.published_at is None


@pytest.mark.django_db
def test_legacy_event_capacity_may_remain_null():
    category = Category.objects.create(
        name="Legacy Phase 2",
    )

    start = timezone.now()

    event = Event.objects.create(
        category=category,
        name="Legacy sans capacité",
        starts_at=start,
        ends_at=start + datetime.timedelta(hours=1),
        capacity_total=None,
    )

    assert event.capacity_total is None


@pytest.mark.django_db
def test_non_null_event_capacity_must_be_positive():
    category = Category.objects.create(
        name="Capacity Constraint",
    )

    start = timezone.now()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Event.objects.create(
                category=category,
                name="Capacité invalide",
                starts_at=start,
                ends_at=start + datetime.timedelta(hours=1),
                capacity_total=0,
            )


@pytest.mark.django_db
def test_ticket_category_exposes_availability(event):
    category = TicketCategory.objects.create(
        event=event,
        name="Tribune Honneur",
        quota=500,
        sold_count=125,
        unit_price_cents=7500,
    )

    assert category.available_count == 375


@pytest.mark.django_db
def test_ticket_category_quota_must_be_positive(event):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TicketCategory.objects.create(
                event=event,
                name="Quota invalide",
                quota=0,
                unit_price_cents=3500,
            )


@pytest.mark.django_db
def test_ticket_category_cannot_oversell(event):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TicketCategory.objects.create(
                event=event,
                name="Survente",
                quota=10,
                sold_count=11,
                unit_price_cents=3500,
            )


@pytest.mark.django_db
def test_ticket_category_name_is_unique_per_event(event):
    TicketCategory.objects.create(
        event=event,
        name="Virage Nord",
        quota=1000,
        unit_price_cents=3500,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TicketCategory.objects.create(
                event=event,
                name="virage nord",
                quota=500,
                unit_price_cents=4000,
            )
