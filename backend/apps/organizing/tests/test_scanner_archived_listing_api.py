from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    SCANNER_DELETED,
    SCANNER_INVITATION_CANCELLED,
)
from apps.organizing.models import Organizer, Scanner

User = get_user_model()

URL = "/api/v1/organizers/me/scanners/archived"
PASSWORD = "Organisateur-Solide-2026!"


def make_user(
    *,
    email,
    role,
    first_name,
    last_name,
):
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
        email="archives-owner@example.test",
        role=roles["ORGANIZER"],
        first_name="Owner",
        last_name="Archives",
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name="Archives Org",
        contact_email="archives-org@example.test",
        validation_status=ORGANIZER_APPROVED,
    )

    return owner, organizer


def make_archived_scanner(
    *,
    roles,
    organizer,
    owner,
    index,
    first_name,
    last_name,
    status,
):
    email = f"archived-{index}@example.test"

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
        removed_at=timezone.now(),
        removed_by=owner,
        archived_at=timezone.now(),
        archived_by=owner,
    )


@pytest.mark.django_db
def test_archived_scanners_are_paginated_five_per_page(
    roles,
):
    owner, organizer = make_context(roles)

    for index in range(7):
        make_archived_scanner(
            roles=roles,
            organizer=organizer,
            owner=owner,
            index=index,
            first_name=f"Prenom{index}",
            last_name=f"Nom{index}",
            status=SCANNER_DELETED,
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
    assert len(second.data["results"]) == 2
    assert second.data["previous"] is not None
    assert second.data["next"] is None


@pytest.mark.django_db
def test_archived_scanner_search_matches_name_and_email(
    roles,
):
    owner, organizer = make_context(roles)

    target = make_archived_scanner(
        roles=roles,
        organizer=organizer,
        owner=owner,
        index=10,
        first_name="Leila",
        last_name="Mansouri",
        status=SCANNER_DELETED,
    )

    make_archived_scanner(
        roles=roles,
        organizer=organizer,
        owner=owner,
        index=11,
        first_name="Autre",
        last_name="Scanner",
        status=SCANNER_DELETED,
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    for search in (
        "leila",
        "MANSOURI",
        "archived-10@example.test",
        "Leila Mansouri",
        "Mansouri Leila",
        "Lei Man",
    ):
        response = client.get(
            URL,
            {
                "search": search,
            },
        )

        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == str(target.pk)


@pytest.mark.django_db
def test_archived_scanner_filter_supports_terminal_states(
    roles,
):
    owner, organizer = make_context(roles)

    cancelled = make_archived_scanner(
        roles=roles,
        organizer=organizer,
        owner=owner,
        index=20,
        first_name="Invitation",
        last_name="Annulee",
        status=SCANNER_INVITATION_CANCELLED,
    )

    make_archived_scanner(
        roles=roles,
        organizer=organizer,
        owner=owner,
        index=21,
        first_name="Compte",
        last_name="Retire",
        status=SCANNER_DELETED,
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.get(
        URL,
        {
            "status": SCANNER_INVITATION_CANCELLED,
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(cancelled.pk)


@pytest.mark.django_db
def test_archived_scanner_filter_rejects_non_terminal_state(
    roles,
):
    owner, _ = make_context(roles)

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.get(
        URL,
        {
            "status": "ACTIVE",
        },
    )

    assert response.status_code == 400
