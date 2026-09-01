from __future__ import annotations

import datetime

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.events import (
    CATALOG_EVENT_CANCELLED,
    CATALOG_EVENT_POSTPONED,
    CATALOG_EVENT_SUSPENDED,
)
from apps.catalog.models import (
    Category,
    Event,
)
from apps.core.outbox.models import OutboxEvent

User = get_user_model()
APPROVED = "APPROVED"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(
        name="Lifecycle",
    )


def make_organizer(
    roles,
    *,
    suffix: str,
):
    user = User.objects.create_user(
        email=(f"lifecycle-{suffix}@example.test"),
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
        org_name=f"Lifecycle {suffix}",
        contact_email=(f"contact-{suffix}@example.test"),
        validation_status=APPROVED,
    )

    return user, organizer


def auth(
    client: APIClient,
    user,
) -> APIClient:
    client.force_authenticate(user=user)
    return client


def published_event(
    *,
    organizer,
    category: Category,
    suffix: str,
) -> Event:
    start = timezone.now() + datetime.timedelta(days=20)

    return Event.objects.create(
        organizer=organizer,
        category=category,
        name=f"Lifecycle {suffix}",
        description="Lifecycle test",
        starts_at=start,
        ends_at=(start + datetime.timedelta(hours=3)),
        venue="Stade FANID",
        capacity_total=1000,
        status=Event.PUBLISHED,
        published_at=timezone.now(),
    )


@pytest.mark.django_db
def test_owner_can_postpone_published_event(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="postpone",
    )

    event = published_event(
        organizer=organizer,
        category=category,
        suffix="postpone",
    )

    old_start = event.starts_at
    old_end = event.ends_at

    new_start = old_start + datetime.timedelta(days=7)
    new_end = old_end + datetime.timedelta(days=7)

    response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/postpone",
        {
            "starts_at": new_start.isoformat(),
            "ends_at": new_end.isoformat(),
            "reason": "Indisponibilité du stade",
            "notify_buyers": True,
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 200
    assert response["ETag"] == '"2"'
    assert response.data["status"] == (Event.POSTPONED)
    assert response.data["lifecycle_reason"] == ("Indisponibilité du stade")

    event.refresh_from_db()

    assert event.starts_at == new_start
    assert event.ends_at == new_end
    assert event.postponed_from_starts_at == old_start
    assert event.postponed_from_ends_at == old_end
    assert event.postponed_to_starts_at == new_start
    assert event.postponed_to_ends_at == new_end
    assert event.lifecycle_changed_at is not None

    outbox = OutboxEvent.objects.get(
        event_type=CATALOG_EVENT_POSTPONED,
    )

    assert outbox.aggregate_id == event.pk
    assert outbox.payload["status"] == (Event.POSTPONED)
    assert outbox.payload["notify_buyers"] is True
    assert outbox.payload["refund_requested"] is False
    assert outbox.payload["previous_starts_at"] == old_start.isoformat()


@pytest.mark.django_db
def test_postpone_rejects_incoherent_dates(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="bad-dates",
    )

    event = published_event(
        organizer=organizer,
        category=category,
        suffix="bad-dates",
    )

    response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/postpone",
        {
            "starts_at": event.ends_at.isoformat(),
            "ends_at": event.starts_at.isoformat(),
            "reason": "Test dates",
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 400

    event.refresh_from_db()

    assert event.status == Event.PUBLISHED
    assert OutboxEvent.objects.count() == 0


@pytest.mark.django_db
def test_owner_can_suspend_published_event(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="suspend",
    )

    event = published_event(
        organizer=organizer,
        category=category,
        suffix="suspend",
    )

    response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/suspend",
        {
            "reason": "Décision de sécurité",
            "notify_buyers": True,
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 200
    assert response["ETag"] == '"2"'
    assert response.data["status"] == (Event.SUSPENDED)

    outbox = OutboxEvent.objects.get(
        event_type=CATALOG_EVENT_SUSPENDED,
    )

    assert outbox.payload == {
        "status": Event.SUSPENDED,
        "reason": "Décision de sécurité",
        "notify_buyers": True,
        "refund_requested": False,
    }


@pytest.mark.django_db
def test_owner_can_cancel_suspended_event_and_request_refund(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="cancel",
    )

    event = published_event(
        organizer=organizer,
        category=category,
        suffix="cancel",
    )

    event.status = Event.SUSPENDED
    event.lifecycle_reason = "Suspendu"
    event.lifecycle_changed_at = timezone.now()
    event.save(
        update_fields=[
            "status",
            "lifecycle_reason",
            "lifecycle_changed_at",
        ]
    )

    response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/cancel",
        {
            "reason": "Événement annulé",
            "notify_buyers": True,
            "refund_requested": True,
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 200
    assert response["ETag"] == '"2"'
    assert response.data["status"] == (Event.CANCELLED)

    outbox = OutboxEvent.objects.get(
        event_type=CATALOG_EVENT_CANCELLED,
    )

    assert outbox.payload == {
        "status": Event.CANCELLED,
        "reason": "Événement annulé",
        "notify_buyers": True,
        "refund_requested": True,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action",
    [
        "postpone",
        "suspend",
        "cancel",
    ],
)
def test_draft_cannot_use_published_lifecycle_actions(
    client,
    category,
    roles,
    action,
):
    user, organizer = make_organizer(
        roles,
        suffix=f"draft-{action}",
    )

    start = timezone.now() + datetime.timedelta(days=5)

    event = Event.objects.create(
        organizer=organizer,
        category=category,
        name=f"Draft {action}",
        starts_at=start,
        ends_at=(start + datetime.timedelta(hours=2)),
        venue="Stade",
        capacity_total=100,
    )

    payload = {
        "reason": "Non autorisé",
        "notify_buyers": True,
    }

    if action == "postpone":
        payload.update(
            {
                "starts_at": (start + datetime.timedelta(days=1)).isoformat(),
                "ends_at": (
                    start
                    + datetime.timedelta(
                        days=1,
                        hours=2,
                    )
                ).isoformat(),
            }
        )

    if action == "cancel":
        payload["refund_requested"] = True

    response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/{action}",
        payload,
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == ("INVALID_STATE_TRANSITION")


@pytest.mark.django_db
def test_lifecycle_action_rejects_stale_version(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="stale",
    )

    event = published_event(
        organizer=organizer,
        category=category,
        suffix="stale",
    )

    event.version = 2
    event.save(update_fields=["version"])

    response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/suspend",
        {
            "reason": "Sécurité",
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == ("STALE_RESOURCE")


@pytest.mark.django_db
def test_lifecycle_action_requires_if_match(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="if-match",
    )

    event = published_event(
        organizer=organizer,
        category=category,
        suffix="if-match",
    )

    response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/suspend",
        {
            "reason": "Sécurité",
        },
        format="json",
    )

    assert response.status_code == 428


@pytest.mark.django_db
def test_foreign_event_lifecycle_is_hidden(
    client,
    category,
    roles,
):
    owner_user, owner = make_organizer(
        roles,
        suffix="owner",
    )
    other_user, _ = make_organizer(
        roles,
        suffix="other",
    )

    event = published_event(
        organizer=owner,
        category=category,
        suffix="foreign",
    )

    response = auth(
        client,
        other_user,
    ).post(
        f"/api/v1/events/{event.pk}/suspend",
        {
            "reason": "Tentative étrangère",
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert owner_user.pk != other_user.pk
    assert response.status_code == 404


@pytest.mark.django_db
def test_owner_can_postpone_without_known_new_date(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="postpone-coming-soon",
    )

    event = published_event(
        organizer=organizer,
        category=category,
        suffix="postpone-coming-soon",
    )

    old_start = event.starts_at
    old_end = event.ends_at

    response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/postpone",
        {
            "starts_at": None,
            "ends_at": None,
            "reason": "Nouvelle programmation en attente",
            "notify_buyers": True,
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 200, response.data
    assert response.data["status"] == Event.POSTPONED
    assert response.data["postponed_from_starts_at"] is not None
    assert response.data["postponed_to_starts_at"] is None
    assert response.data["postponed_to_ends_at"] is None

    event.refresh_from_db()

    assert event.starts_at == old_start
    assert event.ends_at == old_end
    assert event.postponed_from_starts_at == old_start
    assert event.postponed_from_ends_at == old_end
    assert event.postponed_to_starts_at is None
    assert event.postponed_to_ends_at is None


@pytest.mark.django_db
def test_postpone_rejects_only_one_new_date(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="postpone-one-date",
    )

    event = published_event(
        organizer=organizer,
        category=category,
        suffix="postpone-one-date",
    )

    response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/postpone",
        {
            "starts_at": (event.starts_at + datetime.timedelta(days=2)).isoformat(),
            "ends_at": None,
            "reason": "Date partielle",
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 400

    event.refresh_from_db()

    assert event.status == Event.PUBLISHED
    assert event.postponed_from_starts_at is None
    assert event.postponed_to_starts_at is None


@pytest.mark.django_db
def test_postponed_event_can_receive_a_new_schedule_later(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="postpone-later-date",
    )

    event = published_event(
        organizer=organizer,
        category=category,
        suffix="postpone-later-date",
    )

    original_start = event.starts_at
    original_end = event.ends_at

    first_response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/postpone",
        {
            "starts_at": None,
            "ends_at": None,
            "reason": "Nouvelle date en attente",
            "notify_buyers": True,
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert first_response.status_code == 200, first_response.data

    event.refresh_from_db()

    assert event.status == Event.POSTPONED
    assert event.postponed_from_starts_at == original_start
    assert event.postponed_from_ends_at == original_end
    assert event.postponed_to_starts_at is None
    assert event.postponed_to_ends_at is None

    new_start = original_start + datetime.timedelta(days=10)
    new_end = original_end + datetime.timedelta(days=10)

    second_response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/postpone",
        {
            "starts_at": new_start.isoformat(),
            "ends_at": new_end.isoformat(),
            "reason": "Nouvelle programmation confirmée",
            "notify_buyers": True,
        },
        format="json",
        HTTP_IF_MATCH=f'"{event.version}"',
    )

    assert second_response.status_code == 200, second_response.data

    event.refresh_from_db()

    assert event.status == Event.POSTPONED

    # L'ancienne programmation reste l'originale.
    assert event.postponed_from_starts_at == original_start
    assert event.postponed_from_ends_at == original_end

    # La nouvelle programmation devient effective.
    assert event.postponed_to_starts_at == new_start
    assert event.postponed_to_ends_at == new_end
    assert event.starts_at == new_start
    assert event.ends_at == new_end


@pytest.mark.django_db
def test_defining_new_date_does_not_require_a_second_reason(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="define-new-date-no-reason",
    )

    event = published_event(
        organizer=organizer,
        category=category,
        suffix="define-new-date-no-reason",
    )

    original_start = event.starts_at
    original_end = event.ends_at

    first_response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/postpone",
        {
            "starts_at": None,
            "ends_at": None,
            "reason": "Météo",
            "notify_buyers": True,
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert first_response.status_code == 200

    new_start = original_start + datetime.timedelta(days=10)
    new_end = original_end + datetime.timedelta(days=10)

    second_response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/postpone",
        {
            "starts_at": new_start.isoformat(),
            "ends_at": new_end.isoformat(),
            "notify_buyers": True,
        },
        format="json",
        HTTP_IF_MATCH='"2"',
    )

    assert second_response.status_code == 200

    event.refresh_from_db()

    assert event.status == Event.POSTPONED
    assert event.lifecycle_reason == "Météo"
    assert event.postponed_from_starts_at == original_start
    assert event.postponed_from_ends_at == original_end
    assert event.postponed_to_starts_at == new_start
    assert event.postponed_to_ends_at == new_end
    assert event.starts_at == new_start
    assert event.ends_at == new_end


@pytest.mark.django_db
def test_initial_postpone_still_requires_reason(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="postpone-requires-reason",
    )

    event = published_event(
        organizer=organizer,
        category=category,
        suffix="postpone-requires-reason",
    )

    response = auth(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/postpone",
        {
            "starts_at": (event.starts_at + datetime.timedelta(days=3)).isoformat(),
            "ends_at": (event.ends_at + datetime.timedelta(days=3)).isoformat(),
            "notify_buyers": True,
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 400

    event.refresh_from_db()

    assert event.status == Event.PUBLISHED
