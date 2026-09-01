from __future__ import annotations

import datetime

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Category, Event

User = get_user_model()

CATEGORIES_URL = "/api/v1/categories"

ORGANIZER_APPROVED = "APPROVED"
ORGANIZER_PENDING = "PENDING"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def make_organizer(
    roles,
    *,
    suffix: str,
    validation_status: str = (ORGANIZER_APPROVED),
):
    user = User.objects.create_user(
        email=(f"category-{suffix}" "@example.test"),
        password=("Chataigne-Orageuse-2026"),
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(
            1990,
            3,
            12,
        ),
        terms_accepted_at=(timezone.now()),
        role=roles["ORGANIZER"],
    )

    Organizer = apps.get_model(
        "organizing",
        "Organizer",
    )

    organizer = Organizer.objects.create(
        user=user,
        org_name=(f"Organisation {suffix}"),
        contact_email=(f"contact-{suffix}" "@example.test"),
        validation_status=(validation_status),
    )

    return user, organizer


def authenticate(
    client: APIClient,
    user,
) -> APIClient:
    client.force_authenticate(user=user)

    return client


@pytest.mark.django_db
def test_approved_organizer_can_create_category(
    client,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="create",
    )

    response = authenticate(
        client,
        user,
    ).post(
        CATEGORIES_URL,
        {
            "name": "Concert privé",
            "description": ("Concert créé par " "l organisateur"),
        },
        format="json",
    )

    assert response.status_code == 201
    assert response["ETag"] == '"1"'

    category = Category.objects.get(pk=response.data["id"])

    assert category.organizer_id == organizer.pk

    assert category.name == "Concert privé"

    assert response.data["is_owned_by_me"] is True

    assert response.data["can_delete"] is True


@pytest.mark.django_db
def test_pending_organizer_cannot_create_category(
    client,
    roles,
):
    user, _ = make_organizer(
        roles,
        suffix="pending",
        validation_status=(ORGANIZER_PENDING),
    )

    response = authenticate(
        client,
        user,
    ).post(
        CATEGORIES_URL,
        {
            "name": ("Catégorie interdite"),
        },
        format="json",
    )

    assert response.status_code == 403

    assert response.data["error"]["code"] == "ORGANIZER_NOT_APPROVED"

    assert not (
        Category.objects.filter(
            name=("Catégorie interdite"),
        ).exists()
    )


@pytest.mark.django_db
def test_duplicate_category_name_is_rejected_case_insensitively(
    client,
    roles,
):
    Category.objects.create(
        name="Football",
        description="Système",
    )

    user, _ = make_organizer(
        roles,
        suffix="duplicate",
    )

    response = authenticate(
        client,
        user,
    ).post(
        CATEGORIES_URL,
        {
            "name": "football",
        },
        format="json",
    )

    assert response.status_code == 409

    assert response.data["error"]["code"] == "CATEGORY_ALREADY_EXISTS"


@pytest.mark.django_db
def test_list_exposes_category_ownership_and_deletability(
    client,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="list-owner",
    )

    _, other = make_organizer(
        roles,
        suffix="list-other",
    )

    system = Category.objects.create(
        name="Système",
    )

    own_unused = Category.objects.create(
        organizer=organizer,
        name="Ma catégorie libre",
    )

    own_used = Category.objects.create(
        organizer=organizer,
        name="Ma catégorie utilisée",
    )

    foreign = Category.objects.create(
        organizer=other,
        name="Catégorie tierce",
    )

    Event.objects.create(
        organizer=organizer,
        category=own_used,
        name="Événement existant",
        starts_at=timezone.now(),
        ends_at=(timezone.now() + datetime.timedelta(hours=2)),
    )

    response = authenticate(
        client,
        user,
    ).get(CATEGORIES_URL)

    assert response.status_code == 200

    by_id = {item["id"]: item for item in response.data}

    assert by_id[str(system.pk)]["is_owned_by_me"] is False

    assert by_id[str(system.pk)]["can_delete"] is False

    assert by_id[str(own_unused.pk)]["is_owned_by_me"] is True

    assert by_id[str(own_unused.pk)]["can_delete"] is True

    assert by_id[str(own_used.pk)]["is_owned_by_me"] is True

    assert by_id[str(own_used.pk)]["can_delete"] is False

    assert by_id[str(foreign.pk)]["is_owned_by_me"] is False

    assert by_id[str(foreign.pk)]["can_delete"] is False


@pytest.mark.django_db
def test_owner_can_delete_unused_category(
    client,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="delete",
    )

    category = Category.objects.create(
        organizer=organizer,
        name="Temporaire",
    )

    response = authenticate(
        client,
        user,
    ).delete((f"{CATEGORIES_URL}/" f"{category.pk}"))

    assert response.status_code == 204

    assert not (Category.objects.filter(pk=category.pk).exists())


@pytest.mark.django_db
def test_used_category_cannot_be_deleted(
    client,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="used",
    )

    category = Category.objects.create(
        organizer=organizer,
        name="Utilisée",
    )

    Event.objects.create(
        organizer=organizer,
        category=category,
        name=("Événement utilisant " "la catégorie"),
        starts_at=timezone.now(),
        ends_at=(timezone.now() + datetime.timedelta(hours=2)),
    )

    response = authenticate(
        client,
        user,
    ).delete((f"{CATEGORIES_URL}/" f"{category.pk}"))

    assert response.status_code == 409

    assert response.data["error"]["code"] == "CATEGORY_IN_USE"

    assert Category.objects.filter(pk=category.pk).exists()


@pytest.mark.django_db
def test_system_category_cannot_be_deleted_by_organizer(
    client,
    roles,
):
    user, _ = make_organizer(
        roles,
        suffix="system",
    )

    category = Category.objects.create(
        name="Catégorie système",
    )

    response = authenticate(
        client,
        user,
    ).delete((f"{CATEGORIES_URL}/" f"{category.pk}"))

    assert response.status_code == 403

    assert Category.objects.filter(pk=category.pk).exists()


@pytest.mark.django_db
def test_foreign_category_cannot_be_deleted(
    client,
    roles,
):
    user, _ = make_organizer(
        roles,
        suffix="owner",
    )

    _, other = make_organizer(
        roles,
        suffix="other",
    )

    category = Category.objects.create(
        organizer=other,
        name=("Catégorie autre " "organisation"),
    )

    response = authenticate(
        client,
        user,
    ).delete((f"{CATEGORIES_URL}/" f"{category.pk}"))

    assert response.status_code == 403

    assert Category.objects.filter(pk=category.pk).exists()
