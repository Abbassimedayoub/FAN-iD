from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters import notifications
from apps.core.adapters.notifications import InMemorySender
from apps.identity.api import USER_PHONE_CHANGED
from apps.identity.models import User
from apps.organizing import scanner_consumers
from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    SCANNER_ACTIVE,
)
from apps.organizing.models import (
    Organizer,
    Scanner,
)
from apps.organizing.scanner_consumers import (
    ScannerLifecycleConsumer,
)
from apps.organizing.scanner_tasks import (
    send_scanner_phone_changed_organizer_email,
)


@pytest.fixture
def scanner_context(
    db,
    roles,
):
    owner = User.objects.create_user(
        email="owner-phone@example.test",
        password="Owner-Phone-2026!",
        first_name="Olivia",
        last_name="Owner",
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
        org_name="Phone Notification Org",
        contact_email=(
            "organizer-phone@example.test"
        ),
        validation_status=(
            ORGANIZER_APPROVED
        ),
    )

    scanner_user = User(
        email=(
            "scanner-phone-notify"
            "@example.test"
        ),
        first_name="Amine",
        last_name="Scanner",
        phone="+216 20 000 000",
        role=roles["SCANNER"],
        date_of_birth=None,
        terms_accepted_at=None,
        must_change_password=False,
        is_active=True,
    )
    scanner_user.set_password(
        "Scanner-Phone-2026!",
    )
    scanner_user.save()

    scanner = Scanner.objects.create(
        organizer=organizer,
        user=scanner_user,
        invited_by=owner,
        invited_first_name="Amine",
        invited_last_name="Scanner",
        invited_email=(
            scanner_user.email
        ),
        status=SCANNER_ACTIVE,
        activated_at=timezone.now(),
    )

    return (
        owner,
        organizer,
        scanner,
    )


@pytest.mark.django_db
def test_organizer_receives_changed_scanner_phone(
    scanner_context,
    monkeypatch,
):
    (
        _,
        organizer,
        scanner,
    ) = scanner_context

    sender = InMemorySender()

    monkeypatch.setattr(
        notifications,
        "build_notification_sender",
        lambda: sender,
    )

    send_scanner_phone_changed_organizer_email.run(
        scanner_id=str(
            scanner.pk,
        ),
        first_record=False,
    )

    assert len(
        sender.emails_sent,
    ) == 1

    email = sender.emails_sent[0]

    assert email["to"] == (
        organizer.contact_email
    )

    assert email["subject"] == (
        "[FANID] Numéro de téléphone "
        "du scanner modifié"
    )

    assert (
        "Le numéro de téléphone de "
        "Amine Scanner est devenu "
        "+216 20 000 000."
        in email["body"]
    )


@pytest.mark.django_db
def test_organizer_receives_first_scanner_phone_wording(
    scanner_context,
    monkeypatch,
):
    (
        _,
        organizer,
        scanner,
    ) = scanner_context

    sender = InMemorySender()

    monkeypatch.setattr(
        notifications,
        "build_notification_sender",
        lambda: sender,
    )

    send_scanner_phone_changed_organizer_email.run(
        scanner_id=str(
            scanner.pk,
        ),
        first_record=True,
    )

    email = sender.emails_sent[0]

    assert email["to"] == (
        organizer.contact_email
    )

    assert (
        "Le numéro de téléphone de "
        "Amine Scanner a été enregistré : "
        "+216 20 000 000."
        in email["body"]
    )


@pytest.mark.django_db
def test_phone_event_dispatches_organizer_notification(
    scanner_context,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    (
        _,
        _,
        scanner,
    ) = scanner_context

    delayed: list[
        dict[str, object]
    ] = []

    monkeypatch.setattr(
        scanner_consumers
        .send_scanner_phone_changed_organizer_email,
        "delay",
        lambda **kwargs: delayed.append(
            kwargs,
        ),
    )

    event = SimpleNamespace(
        event_type=USER_PHONE_CHANGED,
        aggregate_id=scanner.user_id,
        payload={
            "first_record": False,
        },
    )

    consumer = ScannerLifecycleConsumer()

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        with transaction.atomic():
            consumer.handle(
                event,
            )

    assert delayed == [
        {
            "scanner_id": str(
                scanner.pk,
            ),
            "first_record": False,
        }
    ]


@pytest.mark.django_db
def test_organizer_web_api_reads_current_scanner_phone(
    scanner_context,
):
    (
        owner,
        _,
        scanner,
    ) = scanner_context

    scanner.user.phone = (
        "+216 21 111 111"
    )
    scanner.user.save(
        update_fields=[
            "phone",
            "updated_at",
        ],
    )

    client = APIClient()
    client.force_authenticate(
        user=owner,
    )

    response = client.get(
        "/api/v1/organizers/me/scanners"
    )

    assert response.status_code == 200
    assert response.data["count"] == 1

    scanner_data = (
        response.data["results"][0]
    )

    assert scanner_data["id"] == str(
        scanner.pk,
    )
    assert scanner_data["phone"] == (
        "+216 21 111 111"
    )
