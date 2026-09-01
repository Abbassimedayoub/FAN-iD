from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    SCANNER_ACTIVE,
    SCANNER_CREDENTIAL_REQUEST_FULFILLED,
    SCANNER_CREDENTIAL_REQUEST_PENDING,
)
from apps.organizing.models import Organizer, Scanner, ScannerCredentialRequest

User = get_user_model()

SCANNERS_URL = "/api/v1/organizers/me/scanners"

HELP_URL = "/api/v1/organizers/" "scanner-password-help/request"

OWNER_PASSWORD = "Organisateur-Solide-2026!"


def make_active_scanner(
    roles,
    suffix: str,
):
    owner = User.objects.create_user(
        email=(f"help-owner-{suffix}" "@example.test"),
        password=OWNER_PASSWORD,
        first_name="Nadia",
        last_name="Benali",
        date_of_birth=datetime.date(
            1990,
            1,
            1,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name=f"Help Org {suffix}",
        contact_email=(f"help-contact-{suffix}" "@example.test"),
        validation_status=(ORGANIZER_APPROVED),
    )

    email = f"help-scanner-{suffix}" "@example.test"

    client = APIClient()
    client.force_authenticate(user=owner)

    created = client.post(
        SCANNERS_URL,
        {
            "first_name": "Amine",
            "last_name": "Scanner",
            "email": email,
        },
        format="json",
    )

    assert created.status_code == 201

    scanner = Scanner.objects.get(
        pk=created.data["id"],
    )

    scanner.status = SCANNER_ACTIVE
    scanner.save(
        update_fields=["status"],
    )

    scanner.user.must_change_password = False
    scanner.user.temporary_password_expires_at = None

    scanner.user.save(
        update_fields=[
            "must_change_password",
            "temporary_password_expires_at",
        ],
    )

    return (
        owner,
        organizer,
        scanner,
        email,
    )


@pytest.mark.django_db
def test_unknown_email_returns_generic_202(
    roles,
):
    response = APIClient().post(
        HELP_URL,
        {
            "email": "unknown@example.test",
        },
        format="json",
    )

    assert response.status_code == 202
    assert ScannerCredentialRequest.objects.count() == 0


@pytest.mark.django_db
def test_scanner_creates_pending_request(
    roles,
):
    _, _, scanner, email = make_active_scanner(
        roles,
        "request",
    )

    response = APIClient().post(
        HELP_URL,
        {
            "email": email,
        },
        format="json",
    )

    assert response.status_code == 202

    request = ScannerCredentialRequest.objects.get(
        scanner=scanner,
    )

    assert request.status == SCANNER_CREDENTIAL_REQUEST_PENDING


@pytest.mark.django_db
def test_duplicate_pending_request_is_not_created(
    roles,
):
    _, _, scanner, email = make_active_scanner(
        roles,
        "duplicate",
    )

    client = APIClient()

    assert (
        client.post(
            HELP_URL,
            {"email": email},
            format="json",
        ).status_code
        == 202
    )

    assert (
        client.post(
            HELP_URL,
            {"email": email},
            format="json",
        ).status_code
        == 202
    )

    assert (
        ScannerCredentialRequest.objects.filter(
            scanner=scanner,
            status=(SCANNER_CREDENTIAL_REQUEST_PENDING),
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_organizer_reissues_five_minute_password(
    roles,
):
    owner, _, scanner, email = make_active_scanner(
        roles,
        "reissue",
    )

    initial_generation = scanner.user.temporary_password_generation

    APIClient().post(
        HELP_URL,
        {"email": email},
        format="json",
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        (f"{SCANNERS_URL}/" f"{scanner.pk}/temporary-password"),
        {},
        format="json",
    )

    assert response.status_code == 200

    request = ScannerCredentialRequest.objects.get(
        scanner=scanner,
    )

    assert request.status == SCANNER_CREDENTIAL_REQUEST_FULFILLED

    scanner.user.refresh_from_db()

    assert scanner.user.temporary_password_generation == initial_generation + 1

    assert scanner.user.must_change_password is True

    remaining = scanner.user.temporary_password_expires_at - timezone.now()

    assert remaining > datetime.timedelta(
        minutes=4,
        seconds=45,
    )

    assert remaining <= datetime.timedelta(
        minutes=5,
        seconds=5,
    )


@pytest.mark.django_db
def test_reissue_requires_pending_request(
    roles,
):
    owner, _, scanner, _ = make_active_scanner(
        roles,
        "no-request",
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        (f"{SCANNERS_URL}/" f"{scanner.pk}/temporary-password"),
        {},
        format="json",
    )

    assert response.status_code == 409

    assert response.data["error"]["code"] == "SCANNER_PASSWORD_HELP_NOT_REQUESTED"
