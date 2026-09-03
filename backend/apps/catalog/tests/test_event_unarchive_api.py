from __future__ import annotations

import datetime

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Category, Event

User = get_user_model()
APPROVED = "APPROVED"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(
        name="Unarchive",
    )


def make_organizer(
    roles,
    *,
    suffix: str,
):
    user = User.objects.create_user(
        email=(f"unarchive-{suffix}@example.test"),
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(
            1990,
            3,
            12,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    Organizer = apps.get_model(
        "organizing",
        "Organizer",
    )

    organizer = Organizer.objects.create(
        user=user,
        org_name=f"Unarchive {suffix}",
        contact_email=(f"contact-{suffix}@example.test"),
        validation_status=APPROVED,
        commission_agreed_at=timezone.now(),
    )

    return user, organizer


def archived_event(
    *,
    organizer,
    category: Category,
    suffix: str,
) -> Event:
    start = timezone.now() + datetime.timedelta(days=20)

    return Event.objects.create(
        organizer=organizer,
        category=category,
        name=f"Archived {suffix}",
        starts_at=start,
        ends_at=(start + datetime.timedelta(hours=3)),
        venue="Stade FANID",
        capacity_total=1000,
        status=Event.ARCHIVED,
        published_at=timezone.now(),
    )


@pytest.mark.django_db
def test_owner_can_unarchive_event(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="owner",
    )

    event = archived_event(
        organizer=organizer,
        category=category,
        suffix="owner",
    )

    client.force_authenticate(user=user)

    response = client.post(
        f"/api/v1/events/{event.pk}/unarchive",
        {},
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 200
    assert response["ETag"] == '"2"'
    assert response.data["status"] == (Event.PUBLISHED)
    assert response.data["version"] == 2

    event.refresh_from_db()

    assert event.status == Event.PUBLISHED
    assert event.version == 2


@pytest.mark.django_db
def test_unarchive_requires_if_match(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="match",
    )

    event = archived_event(
        organizer=organizer,
        category=category,
        suffix="match",
    )

    client.force_authenticate(user=user)

    response = client.post(
        f"/api/v1/events/{event.pk}/unarchive",
        {},
        format="json",
    )

    assert response.status_code == 428


@pytest.mark.django_db
def test_unarchive_rejects_stale_version(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="stale",
    )

    event = archived_event(
        organizer=organizer,
        category=category,
        suffix="stale",
    )

    event.version = 2
    event.save(
        update_fields=[
            "version",
        ]
    )

    client.force_authenticate(user=user)

    response = client.post(
        f"/api/v1/events/{event.pk}/unarchive",
        {},
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == ("STALE_RESOURCE")


@pytest.mark.django_db
def test_published_event_cannot_be_unarchived(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="published",
    )

    event = archived_event(
        organizer=organizer,
        category=category,
        suffix="published",
    )

    event.status = Event.PUBLISHED
    event.save(
        update_fields=[
            "status",
        ]
    )

    client.force_authenticate(user=user)

    response = client.post(
        f"/api/v1/events/{event.pk}/unarchive",
        {},
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == ("INVALID_STATE_TRANSITION")


@pytest.mark.django_db
def test_foreign_archived_event_is_hidden(
    client,
    category,
    roles,
):
    _, owner = make_organizer(
        roles,
        suffix="real-owner",
    )

    other_user, _ = make_organizer(
        roles,
        suffix="other",
    )

    event = archived_event(
        organizer=owner,
        category=category,
        suffix="foreign",
    )

    client.force_authenticate(user=other_user)

    response = client.post(
        f"/api/v1/events/{event.pk}/unarchive",
        {},
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 404
