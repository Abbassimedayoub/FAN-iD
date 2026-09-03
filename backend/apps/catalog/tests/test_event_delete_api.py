from __future__ import annotations

import datetime

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Category, Event, TicketCategory

User = get_user_model()

APPROVED = "APPROVED"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(
        name="Suppression événement",
    )


def make_organizer(
    roles,
    *,
    suffix: str,
):
    user = User.objects.create_user(
        email=(f"event-delete-{suffix}" "@example.test"),
        password=("Chataigne-Orageuse-2026"),
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
        org_name=(f"Organisation delete {suffix}"),
        contact_email=(f"delete-{suffix}" "@example.test"),
        validation_status=APPROVED,
        commission_agreed_at=timezone.now(),
    )

    return user, organizer


def make_event(
    *,
    organizer,
    category,
    suffix: str,
    status: str = Event.DRAFT,
) -> Event:
    start = timezone.now() + datetime.timedelta(days=10)

    return Event.objects.create(
        organizer=organizer,
        category=category,
        name=f"Delete event {suffix}",
        description="Suppression sécurisée",
        starts_at=start,
        ends_at=(start + datetime.timedelta(hours=2)),
        venue="FANID Test",
        capacity_total=100,
        status=status,
    )


def authenticate(
    client: APIClient,
    user,
) -> APIClient:
    client.force_authenticate(user=user)

    return client


def event_url(
    event: Event,
) -> str:
    return f"/api/v1/events/{event.pk}"


@pytest.mark.django_db
def test_owner_can_delete_unsold_draft(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="owner",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="owner",
    )

    ticket_category = TicketCategory.objects.create(
        event=event,
        name="Standard",
        quota=100,
        sold_count=0,
        unit_price_cents=2500,
    )

    response = authenticate(
        client,
        user,
    ).delete(
        event_url(event),
        HTTP_IF_MATCH=(f'"{event.version}"'),
    )

    assert response.status_code == 204

    assert not Event.objects.filter(pk=event.pk).exists()

    assert not TicketCategory.objects.filter(pk=ticket_category.pk).exists()


@pytest.mark.django_db
def test_delete_requires_if_match(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="if-match",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="if-match",
    )

    response = authenticate(
        client,
        user,
    ).delete(event_url(event))

    assert response.status_code == 428

    assert response.data["error"]["code"] == "PRECONDITION_REQUIRED"

    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_stale_if_match_cannot_delete_draft(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="stale",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="stale",
    )

    response = authenticate(
        client,
        user,
    ).delete(
        event_url(event),
        HTTP_IF_MATCH='"999"',
    )

    assert response.status_code == 409

    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_published_event_cannot_be_deleted(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="published",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="published",
        status=Event.PUBLISHED,
    )

    response = authenticate(
        client,
        user,
    ).delete(
        event_url(event),
        HTTP_IF_MATCH=(f'"{event.version}"'),
    )

    assert response.status_code == 409

    assert response.data["error"]["code"] == "EVENT_NOT_DRAFT"

    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_draft_with_sales_cannot_be_deleted(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="sales",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="sales",
    )

    TicketCategory.objects.create(
        event=event,
        name="Standard",
        quota=100,
        sold_count=1,
        unit_price_cents=2500,
    )

    response = authenticate(
        client,
        user,
    ).delete(
        event_url(event),
        HTTP_IF_MATCH=(f'"{event.version}"'),
    )

    assert response.status_code == 409

    assert response.data["error"]["code"] == "EVENT_HAS_SALES"

    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_organizer_cannot_delete_foreign_draft(
    client,
    category,
    roles,
):
    user, _ = make_organizer(
        roles,
        suffix="requester",
    )

    _, other = make_organizer(
        roles,
        suffix="other",
    )

    event = make_event(
        organizer=other,
        category=category,
        suffix="foreign",
    )

    response = authenticate(
        client,
        user,
    ).delete(
        event_url(event),
        HTTP_IF_MATCH=(f'"{event.version}"'),
    )

    assert response.status_code == 404

    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.django_db
def test_event_image_deleted_only_after_commit(
    client,
    category,
    roles,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    user, organizer = make_organizer(
        roles,
        suffix="image",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="image",
    )

    event.image_key = "events/test/delete-me.jpg"
    event.save(
        update_fields=[
            "image_key",
        ]
    )

    deleted: list[str] = []

    class FakeStorage:
        def delete(
            self,
            key: str,
        ) -> None:
            deleted.append(key)

    monkeypatch.setattr(
        "apps.catalog.views." "build_object_storage",
        lambda: FakeStorage(),
    )

    with django_capture_on_commit_callbacks(execute=True):
        response = authenticate(
            client,
            user,
        ).delete(
            event_url(event),
            HTTP_IF_MATCH=(f'"{event.version}"'),
        )

        assert deleted == []

    assert response.status_code == 204

    assert deleted == ["events/test/delete-me.jpg"]
