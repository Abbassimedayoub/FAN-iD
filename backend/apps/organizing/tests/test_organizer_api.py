from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizing.constants import ORGANIZER_PENDING
from apps.organizing.models import Organizer

User = get_user_model()

APPLY_URL = "/api/v1/organizers/apply"
ME_URL = "/api/v1/organizers/me"
PASSWORD = "Chataigne-Orageuse-2026"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def fan(db, roles):
    return User.objects.create_user(
        email="organizer-api-fan@example.test",
        password=PASSWORD,
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1996, 5, 4),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


def payload(**overrides) -> dict:
    data = {
        "org_name": "Stade de France",
        "contact_email": "contact@example.test",
        "vat_number": "FR123456789",
    }
    data.update(overrides)
    return data


def authenticate(client: APIClient, user) -> APIClient:
    client.force_authenticate(user=user)
    return client


def test_apply_creates_a_pending_dossier_and_returns_201(client, fan):
    api = authenticate(client, fan)

    response = api.post(APPLY_URL, payload(), format="json")

    assert response.status_code == 201, response.data
    assert response["ETag"] == '"1"'

    organizer = Organizer.objects.get(user_id=fan.pk)

    assert organizer.validation_status == ORGANIZER_PENDING
    assert organizer.version == 1
    assert organizer.org_name == "Stade de France"
    assert organizer.contact_email == "contact@example.test"
    assert organizer.vat_number == "FR123456789"


def test_apply_grants_the_organizer_role_immediately(client, fan):
    api = authenticate(client, fan)

    response = api.post(APPLY_URL, payload(), format="json")

    assert response.status_code == 201, response.data

    fan.refresh_from_db()
    assert fan.role.name == "ORGANIZER"


def test_apply_ignores_privileged_overposting(client, fan):
    api = authenticate(client, fan)

    response = api.post(
        APPLY_URL,
        payload(
            validation_status="APPROVED",
            commission_rate="0.9999",
            rejection_reason="injecte",
            version=999,
        ),
        format="json",
    )

    assert response.status_code == 201, response.data

    organizer = Organizer.objects.get(user_id=fan.pk)

    assert organizer.validation_status == ORGANIZER_PENDING
    assert organizer.version == 1
    assert str(organizer.commission_rate) == "0.0000"
    assert organizer.rejection_reason is None


def test_apply_twice_is_refused_after_role_changes_to_organizer(client, fan):
    api = authenticate(client, fan)

    first = api.post(APPLY_URL, payload(), format="json")
    assert first.status_code == 201, first.data

    fan.refresh_from_db()
    authenticate(client, fan)

    second = api.post(
        APPLY_URL,
        payload(org_name="Autre nom"),
        format="json",
    )

    # ORGANIZER_CREATE est accorde au FAN, pas a ORGANIZER.
    # Le premier apply change immediatement le role en base.
    assert second.status_code == 403, second.data

    organizer = Organizer.objects.get(user_id=fan.pk)
    assert organizer.org_name == "Stade de France"
    assert organizer.version == 1


def test_anonymous_apply_is_refused(client):
    response = client.post(APPLY_URL, payload(), format="json")

    assert response.status_code == 401


def test_me_returns_the_current_dossier_with_etag(client, fan):
    api = authenticate(client, fan)

    created = api.post(APPLY_URL, payload(), format="json")
    assert created.status_code == 201, created.data

    fan.refresh_from_db()
    authenticate(client, fan)

    response = api.get(ME_URL)

    assert response.status_code == 200, response.data
    assert response["ETag"] == '"1"'
    assert response.data["org_name"] == "Stade de France"
    assert response.data["validation_status"] == ORGANIZER_PENDING
    assert response.data["version"] == 1


def test_me_without_a_dossier_is_fail_closed(client, fan):
    api = authenticate(client, fan)

    response = api.get(ME_URL)

    assert response.status_code in {403, 404}


def test_me_never_returns_another_organizers_dossier(client, fan, roles):
    other = User.objects.create_user(
        email="other-organizer@example.test",
        password=PASSWORD,
        first_name="Nora",
        last_name="Amari",
        date_of_birth=datetime.date(1992, 4, 7),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )
    Organizer.objects.create(
        user=other,
        org_name="Autre Organisation",
        contact_email="other@example.test",
    )

    api = authenticate(client, fan)
    response = api.get(ME_URL)

    assert response.status_code in {403, 404}
    assert "Autre Organisation" not in str(response.data)
