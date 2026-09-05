import datetime

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.catalog.lifecycle import (
    OPERATIONAL_ARCHIVED,
    OPERATIONAL_CANCELLED,
    OPERATIONAL_COMING_SOON,
    OPERATIONAL_DRAFT,
    OPERATIONAL_ENDED,
    OPERATIONAL_LIVE,
    OPERATIONAL_POSTPONED,
    OPERATIONAL_SALE_CLOSED,
    OPERATIONAL_SALE_OPEN,
    OPERATIONAL_SUSPENDED,
    event_catalog_status,
    event_operational_status,
    event_sales_open,
    event_sales_phase,
)
from apps.catalog.models import Category, Event


def make_event(
    *,
    status: str,
    now: datetime.datetime,
    sales_starts_at: datetime.datetime | None = None,
    sales_ends_at: datetime.datetime | None = None,
) -> Event:
    category = Category.objects.create(
        name=f"Lifecycle {status} {now.timestamp()}",
    )

    return Event.objects.create(
        category=category,
        name=f"Lifecycle event {status} {now.timestamp()}",
        status=status,
        starts_at=now + datetime.timedelta(hours=4),
        ends_at=now + datetime.timedelta(hours=7),
        sales_starts_at=sales_starts_at,
        sales_ends_at=sales_ends_at,
    )


@pytest.mark.django_db
def test_published_before_sales_window_is_coming_soon():
    now = timezone.now()

    event = make_event(
        status=Event.PUBLISHED,
        now=now,
        sales_starts_at=now + datetime.timedelta(hours=1),
        sales_ends_at=now + datetime.timedelta(hours=3),
    )

    assert event_operational_status(
        event,
        at=now,
    ) == OPERATIONAL_COMING_SOON


@pytest.mark.django_db
def test_published_inside_sales_window_is_sale_open():
    now = timezone.now()

    event = make_event(
        status=Event.PUBLISHED,
        now=now,
        sales_starts_at=now - datetime.timedelta(hours=1),
        sales_ends_at=now + datetime.timedelta(hours=2),
    )

    assert event_operational_status(
        event,
        at=now,
    ) == OPERATIONAL_SALE_OPEN


@pytest.mark.django_db
def test_published_after_sales_window_before_event_is_sale_closed():
    now = timezone.now()

    event = make_event(
        status=Event.PUBLISHED,
        now=now,
        sales_starts_at=now - datetime.timedelta(hours=3),
        sales_ends_at=now - datetime.timedelta(hours=1),
    )

    assert event_operational_status(
        event,
        at=now,
    ) == OPERATIONAL_SALE_CLOSED


@pytest.mark.django_db
def test_legacy_published_without_sales_dates_remains_sale_open():
    now = timezone.now()

    event = make_event(
        status=Event.PUBLISHED,
        now=now,
    )

    assert event_operational_status(
        event,
        at=now,
    ) == OPERATIONAL_SALE_OPEN


@pytest.mark.django_db
def test_published_event_becomes_live_at_start():
    now = timezone.now()

    event = make_event(
        status=Event.PUBLISHED,
        now=now,
    )

    assert event_operational_status(
        event,
        at=event.starts_at,
    ) == OPERATIONAL_LIVE


@pytest.mark.django_db
def test_published_event_becomes_ended_at_end():
    now = timezone.now()

    event = make_event(
        status=Event.PUBLISHED,
        now=now,
    )

    assert event_operational_status(
        event,
        at=event.ends_at,
    ) == OPERATIONAL_ENDED


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (Event.DRAFT, OPERATIONAL_DRAFT),
        (Event.POSTPONED, OPERATIONAL_POSTPONED),
        (Event.SUSPENDED, OPERATIONAL_SUSPENDED),
        (Event.CANCELLED, OPERATIONAL_CANCELLED),
        (Event.ARCHIVED, OPERATIONAL_ARCHIVED),
    ],
)
def test_structural_status_has_priority(
    status,
    expected,
):
    now = timezone.now()

    event = make_event(
        status=status,
        now=now,
        sales_starts_at=now - datetime.timedelta(days=1),
        sales_ends_at=now + datetime.timedelta(days=1),
    )

    assert event_operational_status(
        event,
        at=now,
    ) == expected


@pytest.mark.django_db
def test_model_property_uses_operational_engine():
    now = timezone.now()

    event = make_event(
        status=Event.DRAFT,
        now=now,
    )

    assert event.operational_status == OPERATIONAL_DRAFT


@pytest.mark.django_db
def test_database_rejects_inverted_sales_window():
    now = timezone.now()

    category = Category.objects.create(
        name="Invalid sales window",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Event.objects.create(
                category=category,
                name="Invalid sales window event",
                starts_at=now + datetime.timedelta(hours=4),
                ends_at=now + datetime.timedelta(hours=7),
                sales_starts_at=now + datetime.timedelta(hours=3),
                sales_ends_at=now + datetime.timedelta(hours=2),
            )



@pytest.mark.django_db
def test_postponed_without_new_date_is_not_sellable():
    now = timezone.now()

    event = make_event(
        status=Event.POSTPONED,
        now=now,
        sales_starts_at=now - datetime.timedelta(hours=1),
        sales_ends_at=now + datetime.timedelta(hours=2),
    )

    assert event.postponed_to_starts_at is None
    assert (
        event_sales_phase(event, at=now)
        == OPERATIONAL_POSTPONED
    )
    assert event_sales_open(event, at=now) is False


@pytest.mark.django_db
def test_postponed_with_known_new_date_can_reopen_sales():
    now = timezone.now()

    event = make_event(
        status=Event.POSTPONED,
        now=now,
        sales_starts_at=now - datetime.timedelta(hours=1),
        sales_ends_at=now + datetime.timedelta(hours=2),
    )

    event.postponed_to_starts_at = event.starts_at
    event.postponed_to_ends_at = event.ends_at

    assert (
        event_sales_phase(event, at=now)
        == OPERATIONAL_SALE_OPEN
    )
    assert event_sales_open(event, at=now) is True


@pytest.mark.django_db
def test_catalog_status_becomes_sold_out_during_open_sale():
    now = timezone.now()

    event = make_event(
        status=Event.PUBLISHED,
        now=now,
        sales_starts_at=now - datetime.timedelta(hours=1),
        sales_ends_at=now + datetime.timedelta(hours=2),
    )

    assert event_catalog_status(
        event,
        sold_out=True,
        at=now,
    ) == "SOLD_OUT"

    assert event_catalog_status(
        event,
        sold_out=False,
        at=now,
    ) == OPERATIONAL_SALE_OPEN


@pytest.mark.django_db
def test_sold_out_does_not_hide_coming_soon():
    now = timezone.now()

    event = make_event(
        status=Event.PUBLISHED,
        now=now,
        sales_starts_at=now + datetime.timedelta(hours=1),
        sales_ends_at=now + datetime.timedelta(hours=2),
    )

    assert event_catalog_status(
        event,
        sold_out=True,
        at=now,
    ) == OPERATIONAL_COMING_SOON
