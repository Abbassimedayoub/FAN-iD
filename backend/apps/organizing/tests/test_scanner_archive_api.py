from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    SCANNER_ACTIVE,
    SCANNER_DELETED,
    SCANNER_INVITATION_CANCELLED,
)
from apps.organizing.models import Organizer, Scanner

User = get_user_model()

URL = "/api/v1/organizers/me/scanners/archive"


def make_user(*, email, role):
    return User.objects.create_user(
        email=email,
        password="Strong-Test-Password-2026!",
        first_name="Test",
        last_name="User",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=role,
    )


def make_organizer(*, roles, suffix):
    owner = make_user(
        email=f"archive-owner-{suffix}@example.test",
        role=roles["ORGANIZER"],
    )
    organizer = Organizer.objects.create(
        user=owner,
        org_name=f"Archive Org {suffix}",
        contact_email=f"archive-{suffix}@example.test",
        validation_status=ORGANIZER_APPROVED,
    )
    return owner, organizer


def make_scanner(*, roles, organizer, owner, suffix, status):
    user = make_user(
        email=f"archive-scanner-{suffix}@example.test",
        role=roles["SCANNER"],
    )
    return Scanner.objects.create(
        organizer=organizer,
        user=user,
        invited_by=owner,
        invited_first_name="Ancien",
        invited_last_name="Scanner",
        invited_email=f"archive-scanner-{suffix}@example.test",
        status=status,
        removed_at=timezone.now() if status != SCANNER_ACTIVE else None,
        removed_by=owner if status != SCANNER_ACTIVE else None,
    )


@pytest.mark.django_db
def test_bulk_archive_hides_terminal_scanners(roles):
    owner, organizer = make_organizer(
        roles=roles,
        suffix="success",
    )

    first = make_scanner(
        roles=roles,
        organizer=organizer,
        owner=owner,
        suffix="cancelled",
        status=SCANNER_INVITATION_CANCELLED,
    )
    second = make_scanner(
        roles=roles,
        organizer=organizer,
        owner=owner,
        suffix="deleted",
        status=SCANNER_DELETED,
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        URL,
        {
            "scanners": [
                {"id": str(first.pk), "version": first.version},
                {"id": str(second.pk), "version": second.version},
            ],
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data == {"archived": 2}

    first.refresh_from_db()
    second.refresh_from_db()

    assert first.archived_at is not None
    assert second.archived_at is not None
    assert first.archived_by_id == owner.pk
    assert second.archived_by_id == owner.pk

    listing = client.get("/api/v1/organizers/me/scanners")

    assert listing.status_code == 200
    ids = {item["id"] for item in listing.data["results"]}
    assert str(first.pk) not in ids
    assert str(second.pk) not in ids


@pytest.mark.django_db
def test_bulk_archive_rejects_active_scanner(roles):
    owner, organizer = make_organizer(
        roles=roles,
        suffix="active",
    )

    scanner = make_scanner(
        roles=roles,
        organizer=organizer,
        owner=owner,
        suffix="active",
        status=SCANNER_ACTIVE,
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        URL,
        {
            "scanners": [
                {"id": str(scanner.pk), "version": scanner.version},
            ],
        },
        format="json",
    )

    assert response.status_code == 409

    scanner.refresh_from_db()
    assert scanner.archived_at is None


@pytest.mark.django_db
def test_bulk_archive_rejects_foreign_scanner(roles):
    owner, organizer = make_organizer(
        roles=roles,
        suffix="owner",
    )
    other_owner, other_organizer = make_organizer(
        roles=roles,
        suffix="other",
    )

    scanner = make_scanner(
        roles=roles,
        organizer=other_organizer,
        owner=other_owner,
        suffix="foreign",
        status=SCANNER_DELETED,
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        URL,
        {
            "scanners": [
                {"id": str(scanner.pk), "version": scanner.version},
            ],
        },
        format="json",
    )

    assert response.status_code == 404

    scanner.refresh_from_db()
    assert scanner.archived_at is None
