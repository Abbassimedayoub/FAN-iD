from __future__ import annotations

import datetime

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Category, Event
User = get_user_model()

# Valeurs du contrat HTTP utilisées par ces tests d intégration.
# Le modèle organizing est obtenu via le registre Django afin que le module
# de test catalog ne crée pas de dépendance Python vers les internals
# d un autre bounded context.
ORGANIZER_APPROVED = "APPROVED"
ORGANIZER_PENDING = "PENDING"
ORGANIZER_REJECTED = "REJECTED"
ORGANIZER_SUSPENDED = "SUSPENDED"

EVENTS_URL = "/api/v1/events"
CATEGORIES_URL = "/api/v1/categories"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(
        name="Football API",
        description="Football",
    )


def make_organizer(
    roles,
    *,
    suffix: str,
    validation_status: str,
):
    user = User.objects.create_user(
        email=f"event-{suffix}@example.test",
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
        org_name=f"Organisation {suffix}",
        contact_email=(
            f"contact-{suffix}@example.test"
        ),
        validation_status=validation_status,
    )

    return user, organizer


def event_payload(
    category: Category,
    *,
    name: str = "Match FANID",
) -> dict:
    starts_at = (
        timezone.now()
        + datetime.timedelta(days=5)
    )

    return {
        "category_id": str(category.pk),
        "name": name,
        "description": "Premier événement",
        "starts_at": starts_at.isoformat(),
        "ends_at": (
            starts_at
            + datetime.timedelta(hours=2)
        ).isoformat(),
    }


def authenticate(
    client: APIClient,
    user,
) -> APIClient:
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_approved_organizer_can_list_categories(
    client,
    category,
    roles,
):
    user, _ = make_organizer(
        roles,
        suffix="categories",
        validation_status=ORGANIZER_APPROVED,
    )

    response = authenticate(
        client,
        user,
    ).get(CATEGORIES_URL)

    assert response.status_code == 200

    assert [
        item["id"]
        for item in response.data
    ] == [
        str(category.pk)
    ]


@pytest.mark.django_db
def test_approved_organizer_creates_owned_draft(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="create",
        validation_status=ORGANIZER_APPROVED,
    )

    body = event_payload(category)

    # Ces champs ne font pas partie du contrat d écriture.
    body["status"] = "PUBLISHED"
    body["organizer_id"] = (
        "00000000-0000-4000-8000-000000000999"
    )

    response = authenticate(
        client,
        user,
    ).post(
        EVENTS_URL,
        body,
        format="json",
    )

    assert response.status_code == 201
    assert response["ETag"] == '"1"'

    event = Event.objects.get(
        pk=response.data["id"]
    )

    assert event.organizer_id == organizer.pk
    assert event.status == Event.DRAFT

    assert response.data["organizer_id"] == str(
        organizer.pk
    )
    assert response.data["status"] == Event.DRAFT


@pytest.mark.django_db
@pytest.mark.parametrize(
    "validation_status",
    [
        ORGANIZER_PENDING,
        ORGANIZER_REJECTED,
        ORGANIZER_SUSPENDED,
    ],
)
def test_non_approved_organizer_cannot_create(
    client,
    category,
    roles,
    validation_status,
):
    user, _ = make_organizer(
        roles,
        suffix=validation_status.lower(),
        validation_status=validation_status,
    )

    response = authenticate(
        client,
        user,
    ).post(
        EVENTS_URL,
        event_payload(category),
        format="json",
    )

    assert response.status_code == 403
    assert (
        response.data["error"]["code"]
        == "ORGANIZER_NOT_APPROVED"
    )

    assert Event.objects.count() == 0


@pytest.mark.django_db
def test_list_contains_only_current_organizer_events(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="list-owner",
        validation_status=ORGANIZER_APPROVED,
    )

    _, other = make_organizer(
        roles,
        suffix="list-other",
        validation_status=ORGANIZER_APPROVED,
    )

    own = Event.objects.create(
        organizer=organizer,
        category=category,
        name="Mon match",
        starts_at=timezone.now(),
        ends_at=(
            timezone.now()
            + datetime.timedelta(hours=2)
        ),
    )

    Event.objects.create(
        organizer=other,
        category=category,
        name="Match tiers",
        starts_at=timezone.now(),
        ends_at=(
            timezone.now()
            + datetime.timedelta(hours=2)
        ),
    )

    # Legacy : aucune propriété, donc invisible.
    Event.objects.create(
        organizer=None,
        category=category,
        name="Legacy",
        starts_at=timezone.now(),
        ends_at=(
            timezone.now()
            + datetime.timedelta(hours=2)
        ),
    )

    response = authenticate(
        client,
        user,
    ).get(EVENTS_URL)

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert len(response.data["results"]) == 1
    assert (
        response.data["results"][0]["id"]
        == str(own.pk)
    )


@pytest.mark.django_db
def test_foreign_event_is_hidden_as_not_found(
    client,
    category,
    roles,
):
    user, _ = make_organizer(
        roles,
        suffix="reader",
        validation_status=ORGANIZER_APPROVED,
    )

    _, foreign_organizer = make_organizer(
        roles,
        suffix="foreign",
        validation_status=ORGANIZER_APPROVED,
    )

    foreign = Event.objects.create(
        organizer=foreign_organizer,
        category=category,
        name="Événement privé",
        starts_at=timezone.now(),
        ends_at=(
            timezone.now()
            + datetime.timedelta(hours=2)
        ),
    )

    response = authenticate(
        client,
        user,
    ).get(
        f"{EVENTS_URL}/{foreign.pk}"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_owner_can_retrieve_event_and_receives_etag(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="detail",
        validation_status=ORGANIZER_APPROVED,
    )

    event = Event.objects.create(
        organizer=organizer,
        category=category,
        name="Détail",
        starts_at=timezone.now(),
        ends_at=(
            timezone.now()
            + datetime.timedelta(hours=2)
        ),
    )

    response = authenticate(
        client,
        user,
    ).get(
        f"{EVENTS_URL}/{event.pk}"
    )

    assert response.status_code == 200
    assert response["ETag"] == '"1"'
    assert response.data["id"] == str(event.pk)


@pytest.mark.django_db
def test_owner_can_update_event_with_if_match(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="update",
        validation_status=ORGANIZER_APPROVED,
    )

    event = Event.objects.create(
        organizer=organizer,
        category=category,
        name="Ancien nom",
        starts_at=timezone.now(),
        ends_at=(
            timezone.now()
            + datetime.timedelta(hours=2)
        ),
    )

    response = authenticate(
        client,
        user,
    ).patch(
        f"{EVENTS_URL}/{event.pk}",
        {
            "name": "Nouveau nom",
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 200
    assert response["ETag"] == '"2"'
    assert response.data["name"] == "Nouveau nom"
    assert response.data["version"] == 2


@pytest.mark.django_db
def test_update_requires_if_match(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="if-match",
        validation_status=ORGANIZER_APPROVED,
    )

    event = Event.objects.create(
        organizer=organizer,
        category=category,
        name="Version",
        starts_at=timezone.now(),
        ends_at=(
            timezone.now()
            + datetime.timedelta(hours=2)
        ),
    )

    response = authenticate(
        client,
        user,
    ).patch(
        f"{EVENTS_URL}/{event.pk}",
        {
            "name": "Sans version",
        },
        format="json",
    )

    assert response.status_code == 428
    assert (
        response.data["error"]["code"]
        == "PRECONDITION_REQUIRED"
    )


@pytest.mark.django_db
def test_stale_event_update_is_rejected(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="stale",
        validation_status=ORGANIZER_APPROVED,
    )

    event = Event.objects.create(
        organizer=organizer,
        category=category,
        name="Versionné",
        starts_at=timezone.now(),
        ends_at=(
            timezone.now()
            + datetime.timedelta(hours=2)
        ),
    )

    Event.objects.filter(
        pk=event.pk
    ).update(
        version=2
    )

    response = authenticate(
        client,
        user,
    ).patch(
        f"{EVENTS_URL}/{event.pk}",
        {
            "name": "Écriture obsolète",
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409
    assert (
        response.data["error"]["code"]
        == "STALE_RESOURCE"
    )


@pytest.mark.django_db
def test_create_rejects_incoherent_dates(
    client,
    category,
    roles,
):
    user, _ = make_organizer(
        roles,
        suffix="dates",
        validation_status=ORGANIZER_APPROVED,
    )

    start = timezone.now()

    body = event_payload(category)
    body["starts_at"] = start.isoformat()
    body["ends_at"] = (
        start
        - datetime.timedelta(hours=1)
    ).isoformat()

    response = authenticate(
        client,
        user,
    ).post(
        EVENTS_URL,
        body,
        format="json",
    )

    assert response.status_code == 400
    assert Event.objects.count() == 0


@pytest.mark.django_db
def test_same_name_is_allowed_for_different_organizers(
    client,
    category,
    roles,
):
    user_a, organizer_a = make_organizer(
        roles,
        suffix="same-a",
        validation_status=ORGANIZER_APPROVED,
    )

    user_b, organizer_b = make_organizer(
        roles,
        suffix="same-b",
        validation_status=ORGANIZER_APPROVED,
    )

    first = APIClient()
    second = APIClient()

    response_a = authenticate(
        first,
        user_a,
    ).post(
        EVENTS_URL,
        event_payload(
            category,
            name="Même événement",
        ),
        format="json",
    )

    response_b = authenticate(
        second,
        user_b,
    ).post(
        EVENTS_URL,
        event_payload(
            category,
            name="Même événement",
        ),
        format="json",
    )

    assert response_a.status_code == 201
    assert response_b.status_code == 201

    assert Event.objects.filter(
        organizer=organizer_a,
    ).count() == 1

    assert Event.objects.filter(
        organizer=organizer_b,
    ).count() == 1
