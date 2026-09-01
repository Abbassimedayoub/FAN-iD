from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.outbox.models import OutboxEvent
from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    SCANNER_ACTIVE,
    SCANNER_OPENED,
)
from apps.organizing.models import (
    Organizer,
    Scanner,
)
from apps.organizing.scanner_consumers import (
    activate_scanner_if_ready,
)

User = get_user_model()


def make_opened_scanner(
    roles,
    suffix: str,
    *,
    must_change_password: bool,
):
    owner = User.objects.create_user(
        email=(f"phone-owner-{suffix}" "@example.test"),
        password=("Organisateur-Solide-2026!"),
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
        org_name=f"Phone Org {suffix}",
        contact_email=(f"phone-contact-{suffix}" "@example.test"),
        validation_status=(ORGANIZER_APPROVED),
    )

    scanner_user = User(
        email=(f"phone-scanner-{suffix}" "@example.test"),
        first_name="Amine",
        last_name="Scanner",
        role=roles["SCANNER"],
        date_of_birth=None,
        terms_accepted_at=None,
        must_change_password=(must_change_password),
        is_active=True,
    )

    scanner_user.set_password("Scanner-Solide-2026!")

    scanner_user.save()

    scanner = Scanner.objects.create(
        organizer=organizer,
        user=scanner_user,
        invited_by=owner,
        invited_first_name="Amine",
        invited_last_name="Scanner",
        invited_email=scanner_user.email,
        status=SCANNER_OPENED,
        opened_at=timezone.now(),
    )

    return scanner


@pytest.mark.django_db
def test_password_changed_without_phone_does_not_activate(
    roles,
):
    scanner = make_opened_scanner(
        roles,
        "no-phone",
        must_change_password=False,
    )

    result = activate_scanner_if_ready(
        user_id=scanner.user_id,
    )

    assert result is None

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_OPENED
    assert scanner.activated_at is None


@pytest.mark.django_db
def test_phone_and_password_changed_activate_scanner(
    roles,
):
    scanner = make_opened_scanner(
        roles,
        "ready",
        must_change_password=False,
    )

    scanner.user.phone = "+216 20 000 000"

    scanner.user.save(
        update_fields=[
            "phone",
        ],
    )

    result = activate_scanner_if_ready(
        user_id=scanner.user_id,
    )

    assert result is not None

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_ACTIVE
    assert scanner.activated_at is not None


@pytest.mark.django_db
def test_scanner_cannot_add_phone_before_password_change(
    roles,
):
    scanner = make_opened_scanner(
        roles,
        "password-first",
        must_change_password=True,
    )

    client = APIClient()

    client.force_authenticate(user=scanner.user)

    current = client.get("/api/v1/auth/me")

    assert current.status_code == 200

    response = client.patch(
        "/api/v1/auth/me",
        {
            "phone": "+216 20 000 001",
        },
        format="json",
        HTTP_IF_MATCH=(current["ETag"]),
    )

    assert response.status_code == 400

    scanner.user.refresh_from_db()

    assert not scanner.user.phone


@pytest.mark.django_db
def test_phone_patch_publishes_profile_event(
    roles,
):
    scanner = make_opened_scanner(
        roles,
        "profile-event",
        must_change_password=False,
    )

    client = APIClient()

    client.force_authenticate(user=scanner.user)

    current = client.get("/api/v1/auth/me")

    assert current.status_code == 200

    response = client.patch(
        "/api/v1/auth/me",
        {
            "phone": "+216 20 000 002",
        },
        format="json",
        HTTP_IF_MATCH=(current["ETag"]),
    )

    assert response.status_code == 200
    assert response.data["phone"] == "+216 20 000 002"

    event = OutboxEvent.objects.filter(
        event_type=("identity.user.profile_updated"),
        aggregate_id=scanner.user_id,
    ).latest("occurred_at")

    assert "phone" in event.payload["changed_fields"]

    scanner.user.refresh_from_db()

    result = activate_scanner_if_ready(
        user_id=scanner.user_id,
    )

    assert result is not None

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_ACTIVE
