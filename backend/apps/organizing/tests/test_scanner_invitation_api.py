from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.notifications import InMemorySender
from apps.core.outbox.models import OutboxEvent
from apps.identity.api import USER_PASSWORD_CHANGED, derive_scanner_temporary_password
from apps.organizing.api import resolve_organizer_context
from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    ORGANIZER_PENDING,
    SCANNER_ACTIVE,
    SCANNER_EMAIL_SENT,
    SCANNER_OPENED,
)
from apps.organizing.events import SCANNER_INVITED_EVENT
from apps.organizing.models import Organizer, Scanner
from apps.organizing.scanner_consumers import ScannerLifecycleConsumer
from apps.organizing.scanner_tasks import send_scanner_invitation_emails

User = get_user_model()

URL = "/api/v1/organizers/me/scanners"

OWNER_PASSWORD = "Organisateur-Solide-2026!"

NEW_SCANNER_PASSWORD = "Scanner-Nouveau-Solide-2026!"


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    """
    Isole les compteurs de throttle des tests scanner.

    La suite complete partage sinon le cache Redis avec les
    autres tests de login, ce qui peut produire un faux 429.
    """
    settings.CACHES = {
        "default": {
            "BACKEND": ("django.core.cache.backends.locmem." "LocMemCache"),
            "LOCATION": ("scanner-invitation-throttle-tests"),
        }
    }

    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def make_organizer(
    roles,
    *,
    suffix: str,
    validation_status: str = (ORGANIZER_APPROVED),
):
    user = User.objects.create_user(
        email=(f"scanner-owner-{suffix}" "@example.test"),
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
        org_name=f"Scanner Org {suffix}",
        contact_email=(f"scanner-contact-{suffix}" "@example.test"),
        validation_status=(validation_status),
    )

    return user, organizer


def payload(
    email: str,
) -> dict[str, str]:
    return {
        "first_name": "Amine",
        "last_name": "Scanner",
        "email": email,
    }


def invite(
    *,
    owner,
    email: str,
):
    client = APIClient()
    client.force_authenticate(user=owner)

    return client.post(
        URL,
        payload(email),
        format="json",
    )


@pytest.mark.django_db
def test_approved_organizer_invites_scanner(
    roles,
):
    owner, organizer = make_organizer(
        roles,
        suffix="create",
    )

    response = invite(
        owner=owner,
        email=("scanner-create@example.test"),
    )

    assert response.status_code == 201
    assert response.data["status"] == "INVITED"

    scanner = Scanner.objects.get(
        pk=response.data["id"],
    )

    assert scanner.organizer_id == organizer.pk

    assert scanner.invited_by_id == owner.pk

    assert scanner.user.role.name == "SCANNER"

    assert scanner.user.date_of_birth is None

    assert scanner.user.terms_accepted_at is None

    assert scanner.user.must_change_password is True

    event = OutboxEvent.objects.get(
        event_type=SCANNER_INVITED_EVENT,
        aggregate_id=scanner.pk,
    )

    assert event.payload == {}

    assert "password" not in str(event.payload).lower()

    assert scanner.user.email not in str(event.payload)


@pytest.mark.django_db
def test_pending_organizer_cannot_invite(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="pending",
        validation_status=(ORGANIZER_PENDING),
    )

    response = invite(
        owner=owner,
        email=("scanner-pending@example.test"),
    )

    assert response.status_code == 403
    assert not Scanner.objects.exists()


@pytest.mark.django_db
def test_existing_email_is_rejected(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="duplicate",
    )

    User.objects.create_user(
        email="existing@example.test",
        password=OWNER_PASSWORD,
        first_name="Existing",
        last_name="Account",
        date_of_birth=datetime.date(
            1991,
            1,
            1,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )

    response = invite(
        owner=owner,
        email="existing@example.test",
    )

    assert response.status_code == 409

    assert response.data["error"]["code"] == "SCANNER_EMAIL_ALREADY_USED"


@pytest.mark.django_db
def test_list_is_scoped_to_current_organizer(
    roles,
):
    owner, organizer = make_organizer(
        roles,
        suffix="mine",
    )

    other_owner, _ = make_organizer(
        roles,
        suffix="other",
    )

    mine = invite(
        owner=owner,
        email="mine@example.test",
    )

    invite(
        owner=other_owner,
        email="other@example.test",
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.get(URL)

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert len(response.data["results"]) == 1

    assert response.data["results"][0]["id"] == mine.data["id"]

    scanner = Scanner.objects.get(
        pk=mine.data["id"],
    )

    assert scanner.organizer_id == organizer.pk


@pytest.mark.django_db
def test_invitation_emails_both_sides(
    roles,
    monkeypatch,
):
    owner, organizer = make_organizer(
        roles,
        suffix="emails",
    )

    response = invite(
        owner=owner,
        email="email-scanner@example.test",
    )

    scanner = Scanner.objects.get(
        pk=response.data["id"],
    )

    sender = InMemorySender()

    monkeypatch.setattr(
        "apps.organizing.scanner_tasks." "build_notification_sender",
        lambda: sender,
    )

    result = send_scanner_invitation_emails.run(
        scanner_id=str(scanner.pk),
    )

    assert result["sent"] is True
    assert len(sender.emails_sent) == 2

    scanner_mail = next(message for message in sender.emails_sent if message["to"] == scanner.user.email)

    organizer_mail = next(
        message for message in sender.emails_sent if message["to"] == organizer.contact_email
    )

    temporary_password = derive_scanner_temporary_password(
        invitation_id=scanner.pk,
    )

    assert temporary_password in scanner_mail["body"]

    assert scanner.user.email in scanner_mail["body"]

    assert temporary_password not in organizer_mail["body"]

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_EMAIL_SENT

    assert scanner.scanner_email_sent_at is not None

    assert scanner.organizer_email_sent_at is not None


@pytest.mark.django_db
def test_temporary_password_one_login_only(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="one-time",
    )

    response = invite(
        owner=owner,
        email="one-time@example.test",
    )

    scanner = Scanner.objects.get(
        pk=response.data["id"],
    )

    temporary_password = derive_scanner_temporary_password(
        invitation_id=scanner.pk,
    )

    first = APIClient().post(
        "/api/v1/auth/login",
        {
            "email": scanner.user.email,
            "password": temporary_password,
            "client": "web",
        },
        format="json",
    )

    assert first.status_code == 200

    assert first.data["user"]["must_change_password"] is True

    scanner.user.refresh_from_db()

    assert scanner.user.temporary_password_used_at is not None

    second = APIClient().post(
        "/api/v1/auth/login",
        {
            "email": scanner.user.email,
            "password": temporary_password,
            "client": "web",
        },
        format="json",
    )

    assert second.status_code == 401


@pytest.mark.django_db
def test_scanner_has_no_organizer_context_before_password_change(
    roles,
):
    owner, organizer = make_organizer(
        roles,
        suffix="locked",
    )

    response = invite(
        owner=owner,
        email="locked@example.test",
    )

    scanner = Scanner.objects.get(
        pk=response.data["id"],
    )

    organizer_id, approved = resolve_organizer_context(
        user_id=scanner.user_id,
    )

    assert organizer_id is None
    assert approved is False

    scanner.status = SCANNER_OPENED
    scanner.save(
        update_fields=[
            "status",
        ]
    )

    scanner.user.must_change_password = False
    scanner.user.save(
        update_fields=[
            "must_change_password",
        ]
    )

    organizer_id, approved = resolve_organizer_context(
        user_id=scanner.user_id,
    )

    assert organizer_id == organizer.pk
    assert approved is True


@pytest.mark.django_db
def test_password_change_activates_identity(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="activate",
    )

    response = invite(
        owner=owner,
        email="activate@example.test",
    )

    scanner = Scanner.objects.get(
        pk=response.data["id"],
    )

    temporary_password = derive_scanner_temporary_password(
        invitation_id=scanner.pk,
    )

    scanner.status = SCANNER_OPENED
    scanner.save(
        update_fields=[
            "status",
        ]
    )

    client = APIClient()
    client.force_authenticate(user=scanner.user)

    changed = client.post(
        "/api/v1/auth/password/change",
        {
            "current_password": (temporary_password),
            "new_password": (NEW_SCANNER_PASSWORD),
        },
        format="json",
    )

    assert changed.status_code == 204

    scanner.user.refresh_from_db()

    assert scanner.user.must_change_password is False

    event = OutboxEvent.objects.filter(
        event_type=USER_PASSWORD_CHANGED,
        aggregate_id=scanner.user_id,
    ).latest("occurred_at")

    assert event.payload["temporary_credential_replaced"] is True


@pytest.mark.django_db
def test_lifecycle_consumer_opened_and_active(
    roles,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    owner, _ = make_organizer(
        roles,
        suffix="lifecycle",
    )

    response = invite(
        owner=owner,
        email="lifecycle@example.test",
    )

    scanner = Scanner.objects.get(
        pk=response.data["id"],
    )

    delayed: list[str] = []

    monkeypatch.setattr(
        "apps.organizing.scanner_consumers." "send_scanner_milestone_emails.delay",
        lambda **kwargs: delayed.append(kwargs["milestone"]),
    )

    consumer = ScannerLifecycleConsumer()

    opened = SimpleNamespace(
        event_type=("identity.user.logged_in"),
        aggregate_id=scanner.user_id,
        payload={
            "role": "SCANNER",
            "device_bound": False,
        },
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        with transaction.atomic():
            consumer.handle(opened)

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_OPENED

    assert scanner.opened_at is not None

    assert delayed[-1] == "OPENED"

    # Le vrai service de changement de mot
    # de passe retire ce flag AVANT de publier
    # USER_PASSWORD_CHANGED.
    scanner.user.must_change_password = False

    scanner.user.save(
        update_fields=[
            "must_change_password",
        ],
    )

    password_changed = SimpleNamespace(
        event_type=USER_PASSWORD_CHANGED,
        aggregate_id=scanner.user_id,
        payload={
            "temporary_credential_replaced": (True),
        },
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        with transaction.atomic():
            consumer.handle(password_changed)

    scanner.refresh_from_db()

    # Nouveau contrat :
    # mot de passe changé mais téléphone absent
    # => le scanner reste OPENED.
    assert scanner.status == SCANNER_OPENED

    assert scanner.activated_at is None

    assert delayed[-1] == "OPENED"

    scanner.user.phone = "+216 20 000 003"

    scanner.user.save(
        update_fields=[
            "phone",
        ],
    )

    profile_updated = SimpleNamespace(
        event_type=("identity.user.profile_updated"),
        aggregate_id=scanner.user_id,
        payload={
            "changed_fields": [
                "phone",
            ],
        },
    )

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        with transaction.atomic():
            consumer.handle(profile_updated)

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_ACTIVE

    assert scanner.activated_at is not None

    assert delayed[-1] == "ACTIVE"


@pytest.mark.django_db
def test_temporary_password_expires_after_five_minutes(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="temp-expiry",
    )

    before = timezone.now()

    response = invite(
        owner=owner,
        email="temp-expiry@example.test",
    )

    assert response.status_code == 201

    scanner = Scanner.objects.get(
        pk=response.data["id"],
    )

    scanner.user.refresh_from_db()

    assert scanner.user.temporary_password_generation == 1

    expires_at = scanner.user.temporary_password_expires_at

    assert expires_at is not None

    assert expires_at > before + datetime.timedelta(
        minutes=4,
        seconds=50,
    )

    assert expires_at <= before + datetime.timedelta(
        minutes=5,
        seconds=10,
    )

    temporary_password = derive_scanner_temporary_password(
        invitation_id=scanner.pk,
        generation=1,
    )

    scanner.user.temporary_password_expires_at = timezone.now() - datetime.timedelta(
        seconds=1,
    )

    scanner.user.save(
        update_fields=[
            "temporary_password_expires_at",
        ],
    )

    login = APIClient().post(
        "/api/v1/auth/login",
        {
            "email": ("temp-expiry@example.test"),
            "password": (temporary_password),
            "client": "web",
        },
        format="json",
    )

    assert login.status_code == 401

    assert login.data["error"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.django_db
def test_duplicate_scanner_invitation_has_specific_message(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="same-scanner-invite",
    )

    email = "same-scanner-invite@example.test"

    first = invite(
        owner=owner,
        email=email,
    )

    assert first.status_code == 201

    second = invite(
        owner=owner,
        email=email,
    )

    assert second.status_code == 409
    assert second.data["error"]["code"] == "SCANNER_INVITATION_ALREADY_EXISTS"
    assert second.data["error"]["message"] == (
        "Une invitation a déjà été envoyée à ce compte. " "Vous pouvez la renvoyer depuis sa fiche scanner."
    )
