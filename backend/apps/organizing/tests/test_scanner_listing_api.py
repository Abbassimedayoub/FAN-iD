from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizing.constants import ORGANIZER_APPROVED, SCANNER_ACTIVE, SCANNER_EMAIL_SENT
from apps.organizing.models import Organizer, Scanner

User = get_user_model()

URL = "/api/v1/organizers/me/scanners"
PASSWORD = "Organisateur-Solide-2026!"


def make_user(*, email, role, first_name, last_name):
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=role,
    )


def make_context(roles):
    owner = make_user(
        email="listing-owner@example.test",
        role=roles["ORGANIZER"],
        first_name="Owner",
        last_name="Listing",
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name="Listing Org",
        contact_email="listing-org@example.test",
        validation_status=ORGANIZER_APPROVED,
    )

    return owner, organizer


def make_scanner(
    *,
    roles,
    organizer,
    owner,
    index,
    first_name,
    last_name,
    status=SCANNER_ACTIVE,
):
    email = f"listing-{index}@example.test"

    user = make_user(
        email=email,
        role=roles["SCANNER"],
        first_name=first_name,
        last_name=last_name,
    )

    return Scanner.objects.create(
        organizer=organizer,
        user=user,
        invited_by=owner,
        invited_first_name=first_name,
        invited_last_name=last_name,
        invited_email=email,
        status=status,
    )


@pytest.mark.django_db
def test_scanner_list_is_fixed_to_five_per_page(roles):
    owner, organizer = make_context(roles)

    for index in range(7):
        make_scanner(
            roles=roles,
            organizer=organizer,
            owner=owner,
            index=index,
            first_name=f"Prenom{index}",
            last_name=f"Nom{index}",
        )

    client = APIClient()
    client.force_authenticate(user=owner)

    first = client.get(URL)

    assert first.status_code == 200
    assert first.data["count"] == 7
    assert len(first.data["results"]) == 5
    assert first.data["previous"] is None
    assert first.data["next"] is not None

    second = client.get(
        URL,
        {
            "page": 2,
        },
    )

    assert second.status_code == 200
    assert second.data["count"] == 7
    assert len(second.data["results"]) == 2
    assert second.data["previous"] is not None
    assert second.data["next"] is None


@pytest.mark.django_db
def test_scanner_search_matches_first_last_and_email(roles):
    owner, organizer = make_context(roles)

    alpha = make_scanner(
        roles=roles,
        organizer=organizer,
        owner=owner,
        index=10,
        first_name="Nadia",
        last_name="Benali",
    )

    make_scanner(
        roles=roles,
        organizer=organizer,
        owner=owner,
        index=11,
        first_name="Amine",
        last_name="Trabelsi",
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    for search in (
        "nadia",
        "BENALI",
        "listing-10@example.test",
        "Nadia Benali",
        "Benali Nadia",
        "Nad Ben",
    ):
        response = client.get(
            URL,
            {
                "search": search,
            },
        )

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == str(alpha.pk)


@pytest.mark.django_db
def test_scanner_status_filter_is_server_side(roles):
    owner, organizer = make_context(roles)

    make_scanner(
        roles=roles,
        organizer=organizer,
        owner=owner,
        index=20,
        first_name="Active",
        last_name="Scanner",
        status=SCANNER_ACTIVE,
    )

    sent = make_scanner(
        roles=roles,
        organizer=organizer,
        owner=owner,
        index=21,
        first_name="Email",
        last_name="Sent",
        status=SCANNER_EMAIL_SENT,
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.get(
        URL,
        {
            "status": SCANNER_EMAIL_SENT,
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(sent.pk)


@pytest.mark.django_db
def test_scanner_status_filter_rejects_unknown_status(
    roles,
):
    owner, _ = make_context(roles)

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.get(
        URL,
        {
            "status": "UNKNOWN",
        },
    )

    assert response.status_code == 400
