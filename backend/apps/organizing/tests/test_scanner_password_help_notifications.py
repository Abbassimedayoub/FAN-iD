from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.notifications import (
    InMemorySender,
)
from apps.identity.api import (
    derive_scanner_temporary_password,
)
from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    SCANNER_ACTIVE,
)
from apps.organizing.models import (
    Organizer,
    Scanner,
    ScannerCredentialRequest,
)
from apps.organizing.scanner_credential_tasks import (
    send_scanner_password_help_emails,
    send_scanner_password_reissued_emails,
)

User = get_user_model()

SCANNERS_URL = "/api/v1/organizers/me/scanners"

HELP_URL = "/api/v1/organizers/" "scanner-password-help/request"

PASSWORD = "Organisateur-Solide-2026!"


def make_scanner(
    roles,
    suffix: str,
):
    owner = User.objects.create_user(
        email=(f"notify-owner-{suffix}" "@example.test"),
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
        org_name=(f"Notify Org {suffix}"),
        contact_email=(f"notify-contact-{suffix}" "@example.test"),
        validation_status=(ORGANIZER_APPROVED),
    )

    email = f"notify-scanner-{suffix}" "@example.test"

    client = APIClient()

    client.force_authenticate(user=owner)

    response = client.post(
        SCANNERS_URL,
        {
            "first_name": "Amine",
            "last_name": "Scanner",
            "email": email,
        },
        format="json",
    )

    assert response.status_code == 201

    scanner = Scanner.objects.get(
        pk=response.data["id"],
    )

    scanner.status = SCANNER_ACTIVE

    scanner.save(
        update_fields=[
            "status",
        ],
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
def test_help_request_emails_both_parties(
    roles,
    monkeypatch,
):
    _, organizer, scanner, email = make_scanner(
        roles,
        "help",
    )

    response = APIClient().post(
        HELP_URL,
        {
            "email": email,
        },
        format="json",
    )

    assert response.status_code == 202

    request = ScannerCredentialRequest.objects.get(scanner=scanner)

    sender = InMemorySender()

    monkeypatch.setattr(
        "apps.organizing." "scanner_credential_tasks." "build_notification_sender",
        lambda: sender,
    )

    result = send_scanner_password_help_emails.run(
        request_id=str(request.pk),
    )

    assert result["sent"] is True
    assert len(sender.emails_sent) == 2

    recipients = {item["to"] for item in sender.emails_sent}

    assert email in recipients

    assert organizer.contact_email in recipients


@pytest.mark.django_db
def test_reissued_password_is_only_disclosed_to_scanner(
    roles,
    monkeypatch,
):
    owner, organizer, scanner, email = make_scanner(
        roles,
        "reissue",
    )

    response = APIClient().post(
        HELP_URL,
        {
            "email": email,
        },
        format="json",
    )

    assert response.status_code == 202

    client = APIClient()

    client.force_authenticate(user=owner)

    response = client.post(
        (f"{SCANNERS_URL}/" f"{scanner.pk}/temporary-password"),
        {},
        format="json",
    )

    assert response.status_code == 200

    request = ScannerCredentialRequest.objects.get(scanner=scanner)

    sender = InMemorySender()

    monkeypatch.setattr(
        "apps.organizing." "scanner_credential_tasks." "build_notification_sender",
        lambda: sender,
    )

    result = send_scanner_password_reissued_emails.run(
        request_id=str(request.pk),
        generation=(request.generation),
    )

    assert result["sent"] is True
    assert len(sender.emails_sent) == 2

    scanner.user.refresh_from_db()

    temporary_password = derive_scanner_temporary_password(
        invitation_id=scanner.pk,
        generation=request.generation,
    )

    scanner_message = next(item for item in sender.emails_sent if item["to"] == email)

    organizer_message = next(item for item in sender.emails_sent if (item["to"] == organizer.contact_email))

    assert temporary_password in scanner_message["body"]

    assert temporary_password not in organizer_message["body"]

    assert "5 minutes" in scanner_message["body"]
