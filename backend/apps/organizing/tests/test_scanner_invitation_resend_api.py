from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    SCANNER_ACTIVE,
)
from apps.organizing.models import (
    Organizer,
    Scanner,
    ScannerCredentialRequest,
)

User = get_user_model()

PASSWORD = "Organisateur-Solide-2026!"

SCANNERS_URL = "/api/v1/organizers/me/scanners"


def setup_scanner(
    roles,
    suffix: str,
):
    owner = User.objects.create_user(
        email=(f"resend-owner-{suffix}" "@example.test"),
        password=PASSWORD,
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
        org_name=(f"Resend Org {suffix}"),
        contact_email=(f"resend-contact-{suffix}" "@example.test"),
        validation_status=(ORGANIZER_APPROVED),
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        SCANNERS_URL,
        {
            "first_name": "Amine",
            "last_name": "Scanner",
            "email": (f"resend-scanner-{suffix}" "@example.test"),
        },
        format="json",
    )

    assert response.status_code == 201

    scanner = Scanner.objects.get(
        pk=response.data["id"],
    )

    return (
        owner,
        organizer,
        scanner,
    )


@pytest.mark.django_db
def test_pre_active_invitation_can_be_resent_without_help_request(
    roles,
):
    owner, _, scanner = setup_scanner(
        roles,
        "pre-active",
    )

    assert ScannerCredentialRequest.objects.filter(scanner=scanner).count() == 0

    initial_generation = scanner.user.temporary_password_generation

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        (f"{SCANNERS_URL}/" f"{scanner.pk}/resend-invitation"),
        {},
        format="json",
    )

    assert response.status_code == 200

    scanner.user.refresh_from_db()

    assert scanner.user.temporary_password_generation == initial_generation + 1

    assert scanner.user.must_change_password is True

    expires_at = scanner.user.temporary_password_expires_at

    assert expires_at is not None

    remaining = expires_at - timezone.now()

    assert remaining > datetime.timedelta(
        minutes=4,
        seconds=45,
    )

    assert remaining <= datetime.timedelta(
        minutes=5,
        seconds=5,
    )

    assert ScannerCredentialRequest.objects.filter(scanner=scanner).count() == 0


@pytest.mark.django_db
def test_active_scanner_cannot_use_resend_invitation(
    roles,
):
    owner, _, scanner = setup_scanner(
        roles,
        "active",
    )

    scanner.status = SCANNER_ACTIVE

    scanner.save(
        update_fields=[
            "status",
        ],
    )

    scanner.user.must_change_password = False

    scanner.user.save(
        update_fields=[
            "must_change_password",
        ],
    )

    client = APIClient()

    client.force_authenticate(user=owner)

    response = client.post(
        (f"{SCANNERS_URL}/" f"{scanner.pk}/resend-invitation"),
        {},
        format="json",
    )

    assert response.status_code == 409

    assert response.data["error"]["code"] == "SCANNER_INVITATION_RESEND_NOT_ALLOWED"
