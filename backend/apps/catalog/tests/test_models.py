from __future__ import annotations

import datetime

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.catalog.models import Category, Event


@pytest.fixture
def category(db):
    return Category.objects.create(
        name="Concert",
        description="Musique live",
    )


def test_category_can_be_created(category):
    assert category.name == "Concert"
    assert category.version == 1


def test_category_name_is_case_insensitive_unique(category):
    with pytest.raises(IntegrityError):
        Category.objects.create(
            name="concert",
        )


def test_event_can_be_created(category):
    event = Event.objects.create(
        category=category,
        name="Festival FAN",
        starts_at=timezone.now(),
        ends_at=timezone.now() + datetime.timedelta(hours=2),
    )

    assert event.status == Event.DRAFT
    assert event.category_id == category.id


def test_event_status_defaults_to_draft(category):
    event = Event.objects.create(
        category=category,
        name="Expo",
        starts_at=timezone.now(),
        ends_at=timezone.now() + datetime.timedelta(hours=1),
    )

    assert event.status in Event.STATUSES
    assert event.status == Event.DRAFT


def test_event_dates_constraint_is_enforced(category):
    event = Event(
        category=category,
        name="Erreur dates",
        starts_at=timezone.now(),
        ends_at=timezone.now() - datetime.timedelta(hours=1),
    )

    with pytest.raises(IntegrityError):
        event.save()
