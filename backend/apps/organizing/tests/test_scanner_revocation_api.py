from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.notifications import InMemorySender
from apps.core.outbox.models import OutboxEvent
from apps.identity.api import USER_PASSWORD_CHANGED
from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    SCANNER_ACTIVE,
    SCANNER_DELETED,
    SCANNER_INVITATION_CANCELLED,
)
from apps.organizing.events import SCANNER_REVOKED_EVENT
from apps.organizing.models import Organizer, Scanner
from apps.organizing.scanner_consumers import ScannerLifecycleConsumer
from apps.organizing.scanner_security import (
    SCANNER_SECURITY_ACTION_REVOKE,
    ScannerSecurityService,
    derive_scanner_security_code,
)
from apps.organizing.scanner_tasks import send_scanner_invitation_emails, send_scanner_revocation_emails

User = get_user_model()

URL = "/api/v1/organizers/me/scanners"

OWNER_PASSWORD = "Organisateur-Solide-2026!"


def make_organizer(
    roles,
    *,
    suffix: str,
):
    user = User.objects.create_user(
        email=(f"revoke-owner-{suffix}" "@example.test"),
        password=OWNER_PASSWORD,
        first_name="Nadia",
        last_name="Benali",
        date_of_birth=datetime.date(
            1990,
            5,
            2,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    organizer = Organizer.objects.create(
        user=user,
        org_name=(f"Revoke Org {suffix}"),
        contact_email=(f"revoke-contact-{suffix}" "@example.test"),
        validation_status=(ORGANIZER_APPROVED),
    )

    return user, organizer


def invite(
    *,
    owner,
    email: str,
):
    client = APIClient()
    client.force_authenticate(user=owner)

    return client.post(
        URL,
        {
            "first_name": "Amine",
            "last_name": "Scanner",
            "email": email,
        },
        format="json",
    )


def revoke_otp_payload(
    *,
    owner,
    scanner,
):
    organizer = Organizer.objects.get(
        user=owner,
    )

    result = ScannerSecurityService.request(
        organizer=organizer,
        scanner_id=scanner.pk,
        requested_by_id=owner.pk,
        action=SCANNER_SECURITY_ACTION_REVOKE,
    )

    return {
        "challenge_id": str(result.challenge_id),
        "code": derive_scanner_security_code(
            result.challenge_id,
        ),
    }


@pytest.mark.django_db
def test_cancel_invitation_releases_email(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="cancel",
    )

    email = "cancel-scanner@example.test"

    created = invite(
        owner=owner,
        email=email,
    )

    assert created.status_code == 201

    scanner = Scanner.objects.get(
        pk=created.data["id"],
    )

    original_user_id = scanner.user_id

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.delete(
        f"{URL}/{scanner.pk}",
        revoke_otp_payload(
            owner=owner,
            scanner=scanner,
        ),
        format="json",
        HTTP_IF_MATCH=(f'"{scanner.version}"'),
    )

    assert response.status_code == 204

    scanner.refresh_from_db()
    scanner.user.refresh_from_db()

    assert scanner.status == SCANNER_INVITATION_CANCELLED

    assert scanner.removed_at is not None
    assert scanner.removed_by_id == owner.pk

    assert scanner.invited_email == email

    assert scanner.user.is_active is False

    assert scanner.user.anonymized_at is not None

    assert scanner.user.email != email

    assert scanner.user.has_usable_password() is False

    event = OutboxEvent.objects.get(
        event_type=SCANNER_REVOKED_EVENT,
        aggregate_id=scanner.pk,
    )

    assert event.actor_id == owner.pk

    reinvited = invite(
        owner=owner,
        email=email,
    )

    assert reinvited.status_code == 201

    assert reinvited.data["user_id"] != str(original_user_id)


@pytest.mark.django_db
def test_active_scanner_removal_revokes_sessions(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="active",
    )

    created = invite(
        owner=owner,
        email=("active-remove@example.test"),
    )

    scanner = Scanner.objects.get(
        pk=created.data["id"],
    )

    scanner.user.must_change_password = False

    scanner.user.save(
        update_fields=[
            "must_change_password",
        ],
    )

    scanner.status = SCANNER_ACTIVE

    scanner.save(
        update_fields=[
            "status",
        ],
    )

    Session = apps.get_model(
        "identity",
        "Session",
    )

    session = Session.objects.create(
        user=scanner.user,
        family_id=uuid.uuid4(),
        refresh_jti=uuid.uuid4(),
        expires_at=(timezone.now() + datetime.timedelta(days=1)),
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.delete(
        f"{URL}/{scanner.pk}",
        revoke_otp_payload(
            owner=owner,
            scanner=scanner,
        ),
        format="json",
        HTTP_IF_MATCH=(f'"{scanner.version}"'),
    )

    assert response.status_code == 204

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_DELETED

    session.refresh_from_db()

    assert session.revoked_at is not None

    assert session.revoked_reason == "SCANNER_REMOVED"

    scanner.user.refresh_from_db()

    assert scanner.user.is_active is False


@pytest.mark.django_db
def test_revoke_requires_if_match(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="missing-if-match",
    )

    created = invite(
        owner=owner,
        email=("missing-if-match@example.test"),
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.delete(
        f"{URL}/{created.data['id']}",
    )

    assert response.status_code == 428


@pytest.mark.django_db
def test_revoke_rejects_stale_version(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="stale",
    )

    created = invite(
        owner=owner,
        email="stale-remove@example.test",
    )

    scanner = Scanner.objects.get(
        pk=created.data["id"],
    )

    payload = revoke_otp_payload(
        owner=owner,
        scanner=scanner,
    )

    challenge = scanner.revocation_challenges.get(
        pk=payload["challenge_id"],
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.delete(
        f"{URL}/{created.data['id']}",
        payload,
        format="json",
        HTTP_IF_MATCH='"999"',
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "STALE_RESOURCE"

    challenge.refresh_from_db()

    # Un conflit de version ne doit jamais brûler un OTP valide.
    assert challenge.consumed_at is None

    retry = client.delete(
        f"{URL}/{created.data['id']}",
        payload,
        format="json",
        HTTP_IF_MATCH=f'"{scanner.version}"',
    )

    assert retry.status_code == 204

    challenge.refresh_from_db()
    assert challenge.consumed_at is not None


@pytest.mark.django_db
def test_bad_revoke_otp_persists_attempt_without_running_revoke(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="bad-otp-attempt",
    )

    created = invite(
        owner=owner,
        email="bad-otp-attempt@example.test",
    )

    scanner = Scanner.objects.get(
        pk=created.data["id"],
    )

    payload = revoke_otp_payload(
        owner=owner,
        scanner=scanner,
    )

    challenge = scanner.revocation_challenges.get(
        pk=payload["challenge_id"],
    )

    payload["code"] = "000000" if payload["code"] != "000000" else "000001"

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.delete(
        f"{URL}/{scanner.pk}",
        payload,
        format="json",
        HTTP_IF_MATCH=f'"{scanner.version}"',
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "OTP_INVALID"

    challenge.refresh_from_db()
    scanner.refresh_from_db()

    # L'orchestrateur ne doit pas annuler le compteur OTP
    # lorsqu'un mauvais code est saisi.
    assert challenge.attempts == 1
    assert challenge.consumed_at is None

    # Et l'opération destructive ne doit pas avoir été exécutée.
    assert scanner.status == created.data["status"]


@pytest.mark.django_db
def test_foreign_organizer_cannot_revoke(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="owner",
    )

    other, _ = make_organizer(
        roles,
        suffix="other",
    )

    created = invite(
        owner=owner,
        email=("foreign-remove@example.test"),
    )

    scanner = Scanner.objects.get(
        pk=created.data["id"],
    )

    client = APIClient()
    client.force_authenticate(user=other)

    response = client.post(
        f"{URL}/{scanner.pk}/security-code",
        {
            "action": SCANNER_SECURITY_ACTION_REVOKE,
        },
        format="json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_revocation_emails_go_to_both_sides(
    roles,
    monkeypatch,
):
    owner, organizer = make_organizer(
        roles,
        suffix="email",
    )

    email = "revoke-email@example.test"

    created = invite(
        owner=owner,
        email=email,
    )

    scanner = Scanner.objects.get(
        pk=created.data["id"],
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.delete(
        f"{URL}/{scanner.pk}",
        revoke_otp_payload(
            owner=owner,
            scanner=scanner,
        ),
        format="json",
        HTTP_IF_MATCH=(f'"{scanner.version}"'),
    )

    assert response.status_code == 204

    sender = InMemorySender()

    monkeypatch.setattr(
        "apps.organizing.scanner_tasks." "build_notification_sender",
        lambda: sender,
    )

    result = send_scanner_revocation_emails.run(
        scanner_id=str(scanner.pk),
    )

    assert result["sent"] is True

    assert len(sender.emails_sent) == 2

    recipients = {message["to"] for message in sender.emails_sent}

    assert email in recipients

    assert organizer.contact_email in recipients


@pytest.mark.django_db
def test_cancelled_invitation_never_sends_invitation_afterwards(
    roles,
    monkeypatch,
):
    owner, _ = make_organizer(
        roles,
        suffix="late-invite",
    )

    created = invite(
        owner=owner,
        email=("late-invite@example.test"),
    )

    scanner = Scanner.objects.get(
        pk=created.data["id"],
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.delete(
        f"{URL}/{scanner.pk}",
        revoke_otp_payload(
            owner=owner,
            scanner=scanner,
        ),
        format="json",
        HTTP_IF_MATCH=(f'"{scanner.version}"'),
    )

    assert response.status_code == 204

    sender = InMemorySender()

    monkeypatch.setattr(
        "apps.organizing.scanner_tasks." "build_notification_sender",
        lambda: sender,
    )

    result = send_scanner_invitation_emails.run(
        scanner_id=str(scanner.pk),
    )

    assert result == {
        "sent": False,
        "reason": "scanner_revoked",
    }

    assert sender.emails_sent == []


@pytest.mark.django_db
def test_delayed_password_event_cannot_resurrect_cancelled_scanner(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="no-resurrection",
    )

    created = invite(
        owner=owner,
        email=("no-resurrection@example.test"),
    )

    scanner = Scanner.objects.get(
        pk=created.data["id"],
    )

    scanner_user_id = scanner.user_id

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.delete(
        f"{URL}/{scanner.pk}",
        revoke_otp_payload(
            owner=owner,
            scanner=scanner,
        ),
        format="json",
        HTTP_IF_MATCH=(f'"{scanner.version}"'),
    )

    assert response.status_code == 204

    consumer = ScannerLifecycleConsumer()

    consumer.handle(
        SimpleNamespace(
            event_type=USER_PASSWORD_CHANGED,
            aggregate_id=scanner_user_id,
            payload={
                "temporary_credential_replaced": (True),
            },
        )
    )

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_INVITATION_CANCELLED
