from __future__ import annotations

import pytest
from django.utils import timezone

from apps.catalog.events import (
    CATALOG_EVENT_CANCELLED,
    CATALOG_EVENT_POSTPONED,
    CATALOG_EVENT_SCANNER_ASSIGNED,
    CATALOG_EVENT_SCANNER_UNASSIGNED,
    CATALOG_EVENT_SUSPENDED,
)
from apps.catalog.models import (
    Event,
    EventScannerAssignment,
)
from apps.catalog.tests.test_event_scanner_assignment_api import (
    make_event,
    make_organizer,
    make_scanner,
)
from apps.notifying.event_scanner_consumers import (
    EventScannerNotificationConsumer,
)
from apps.notifying.event_scanner_tasks import (
    send_event_scanner_assignment_emails,
    send_event_scanner_lifecycle_emails,
)


class FakeSender:
    def __init__(self):
        self.emails_sent = []

    def send_email(
        self,
        *,
        to,
        subject,
        body,
        **kwargs,
    ):
        self.emails_sent.append(
            {
                "to": to,
                "subject": subject,
                "body": body,
            }
        )


@pytest.mark.django_db
def test_assignment_and_unassignment_email_scanner_and_organizer(
    roles,
    monkeypatch,
):
    owner, organizer = make_organizer(
        roles,
        suffix="notify-assignment",
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="notify-assignment",
        status="ACTIVE",
    )

    event = make_event(
        organizer=organizer,
        suffix="notify-assignment",
    )

    sender = FakeSender()

    monkeypatch.setattr(
        "apps.notifying.event_scanner_tasks."
        "build_notification_sender",
        lambda: sender,
    )

    assigned = (
        send_event_scanner_assignment_emails.run(
            event_id=str(event.pk),
            scanner_id=str(scanner.pk),
            change="ASSIGNED",
        )
    )

    assert assigned["sent"] is True

    recipients = {
        item["to"]
        for item in sender.emails_sent
    }

    assert scanner.invited_email in recipients
    assert organizer.contact_email in recipients

    assert any(
        "Nouvel événement affecté"
        in item["subject"]
        for item in sender.emails_sent
        if item["to"] == scanner.invited_email
    )

    sender.emails_sent.clear()

    unassigned = (
        send_event_scanner_assignment_emails.run(
            event_id=str(event.pk),
            scanner_id=str(scanner.pk),
            change="UNASSIGNED",
        )
    )

    assert unassigned["sent"] is True

    recipients = {
        item["to"]
        for item in sender.emails_sent
    }

    assert scanner.invited_email in recipients
    assert organizer.contact_email in recipients

    assert any(
        "Retrait d’une affectation"
        in item["subject"]
        for item in sender.emails_sent
        if item["to"] == scanner.invited_email
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "event_type,status",
    [
        (
            CATALOG_EVENT_POSTPONED,
            Event.POSTPONED,
        ),
        (
            CATALOG_EVENT_SUSPENDED,
            Event.SUSPENDED,
        ),
        (
            CATALOG_EVENT_CANCELLED,
            Event.CANCELLED,
        ),
    ],
)
def test_lifecycle_email_scanner_and_organizer(
    roles,
    monkeypatch,
    event_type,
    status,
):
    owner, organizer = make_organizer(
        roles,
        suffix=f"notify-{status.lower()}",
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix=f"notify-{status.lower()}",
        status="ACTIVE",
    )

    event = make_event(
        organizer=organizer,
        suffix=f"notify-{status.lower()}",
    )

    EventScannerAssignment.objects.create(
        event=event,
        scanner_id=scanner.pk,
        assigned_by_id=owner.pk,
    )

    event.status = status
    event.lifecycle_reason = "Changement test"
    event.lifecycle_changed_at = timezone.now()
    event.save(
        update_fields=[
            "status",
            "lifecycle_reason",
            "lifecycle_changed_at",
            "updated_at",
        ]
    )

    sender = FakeSender()

    monkeypatch.setattr(
        "apps.notifying.event_scanner_tasks."
        "build_notification_sender",
        lambda: sender,
    )

    result = (
        send_event_scanner_lifecycle_emails.run(
            event_id=str(event.pk),
            change=event_type,
        )
    )

    assert result["sent"] is True
    assert result["scanner_recipients"] == 1

    recipients = {
        item["to"]
        for item in sender.emails_sent
    }

    assert scanner.invited_email in recipients
    assert organizer.contact_email in recipients

    scanner_email = next(
        item
        for item in sender.emails_sent
        if item["to"] == scanner.invited_email
    )

    assert event.name in scanner_email["body"]
    assert "Changement test" in scanner_email["body"]


@pytest.mark.django_db
def test_removed_scanner_no_longer_receives_lifecycle_email(
    roles,
    monkeypatch,
):
    owner, organizer = make_organizer(
        roles,
        suffix="notify-removed",
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="notify-removed",
        status="ACTIVE",
    )

    event = make_event(
        organizer=organizer,
        suffix="notify-removed",
    )

    EventScannerAssignment.objects.create(
        event=event,
        scanner_id=scanner.pk,
        assigned_by_id=owner.pk,
        unassigned_at=timezone.now(),
        unassigned_by_id=owner.pk,
    )

    event.status = Event.CANCELLED
    event.lifecycle_reason = "Annulation test"
    event.lifecycle_changed_at = timezone.now()
    event.save(
        update_fields=[
            "status",
            "lifecycle_reason",
            "lifecycle_changed_at",
            "updated_at",
        ]
    )

    sender = FakeSender()

    monkeypatch.setattr(
        "apps.notifying.event_scanner_tasks."
        "build_notification_sender",
        lambda: sender,
    )

    result = (
        send_event_scanner_lifecycle_emails.run(
            event_id=str(event.pk),
            change=CATALOG_EVENT_CANCELLED,
        )
    )

    assert result["sent"] is True
    assert result["scanner_recipients"] == 0

    recipients = [
        item["to"]
        for item in sender.emails_sent
    ]

    assert scanner.invited_email not in recipients
    assert recipients == [
        organizer.contact_email
    ]


def test_consumer_handles_all_required_event_changes():
    assert (
        EventScannerNotificationConsumer
        .handled_event_types
    ) == {
        CATALOG_EVENT_SCANNER_ASSIGNED,
        CATALOG_EVENT_SCANNER_UNASSIGNED,
        CATALOG_EVENT_POSTPONED,
        CATALOG_EVENT_SUSPENDED,
        CATALOG_EVENT_CANCELLED,
    }
