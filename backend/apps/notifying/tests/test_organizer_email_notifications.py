from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.adapters.notifications import (
    InMemorySender,
)
from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    ORGANIZER_REJECTED,
    ORGANIZER_SUSPENDED,
)
from apps.organizing.events import (
    ORGANIZER_APPROVED_EVENT,
)
from apps.organizing.models import Organizer
from apps.notifying import tasks
from apps.notifying.consumers import (
    OrganizerDecisionEmailConsumer,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


def make_organizer(
    *,
    roles,
    status: str,
    reason: str | None = None,
) -> Organizer:
    user = User.objects.create_user(
        email=f"{uuid.uuid4()}@example.test",
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(
            1990,
            3,
            12,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    return Organizer.objects.create(
        user=user,
        org_name=f"Organisation {uuid.uuid4()}",
        contact_email=user.email,
        validation_status=status,
        rejection_reason=reason,
    )


def test_approved_decision_sends_email_to_account(
    monkeypatch,
    roles,
):
    organizer = make_organizer(
        roles=roles,
        status=ORGANIZER_APPROVED,
    )

    sender = InMemorySender()

    monkeypatch.setattr(
        tasks,
        "build_notification_sender",
        lambda: sender,
    )

    result = tasks.send_organizer_decision_email.run(
        organizer_id=str(organizer.pk),
        decision=ORGANIZER_APPROVED,
    )

    assert result["sent"] is True
    assert len(sender.emails_sent) == 1

    email = sender.emails_sent[0]

    assert email["to"] == organizer.user.email
    assert "approuvée" in email["subject"]
    assert organizer.org_name in email["body"]


def test_rejected_decision_includes_reason(
    monkeypatch,
    roles,
):
    organizer = make_organizer(
        roles=roles,
        status=ORGANIZER_REJECTED,
        reason="Justificatif légal manquant",
    )

    sender = InMemorySender()

    monkeypatch.setattr(
        tasks,
        "build_notification_sender",
        lambda: sender,
    )

    result = tasks.send_organizer_decision_email.run(
        organizer_id=str(organizer.pk),
        decision=ORGANIZER_REJECTED,
    )

    assert result["sent"] is True
    assert len(sender.emails_sent) == 1

    email = sender.emails_sent[0]

    assert email["to"] == organizer.user.email
    assert "Décision" in email["subject"]
    assert "Justificatif légal manquant" in email["body"]


def test_suspended_decision_sends_email_to_account(
    monkeypatch,
    roles,
):
    organizer = make_organizer(
        roles=roles,
        status=ORGANIZER_SUSPENDED,
    )

    sender = InMemorySender()

    monkeypatch.setattr(
        tasks,
        "build_notification_sender",
        lambda: sender,
    )

    result = tasks.send_organizer_decision_email.run(
        organizer_id=str(organizer.pk),
        decision=ORGANIZER_SUSPENDED,
    )

    assert result["sent"] is True
    assert len(sender.emails_sent) == 1

    email = sender.emails_sent[0]

    assert email["to"] == organizer.user.email
    assert "suspendu" in email["subject"].lower()
    assert organizer.org_name in email["body"]


def test_consumer_handles_suspension_event():
    assert "organizing.organizer.suspended" in OrganizerDecisionEmailConsumer.handled_event_types


def test_outbox_consumer_defers_celery_task(
    monkeypatch,
):
    organizer_id = uuid.uuid4()
    calls: list[dict[str, str]] = []

    monkeypatch.setattr(
        OrganizerDecisionEmailConsumer,
        "defer",
        staticmethod(lambda callback: callback()),
    )

    monkeypatch.setattr(
        tasks.send_organizer_decision_email,
        "delay",
        lambda **kwargs: calls.append(kwargs),
    )

    # consumers.py possède sa propre référence au task object :
    from apps.notifying import consumers

    monkeypatch.setattr(
        consumers.send_organizer_decision_email,
        "delay",
        lambda **kwargs: calls.append(kwargs),
    )

    event = SimpleNamespace(
        aggregate_id=organizer_id,
        event_type=ORGANIZER_APPROVED_EVENT,
        payload={"status": ORGANIZER_APPROVED},
    )

    OrganizerDecisionEmailConsumer().handle(event)

    assert calls == [
        {
            "organizer_id": str(organizer_id),
            "decision": ORGANIZER_APPROVED,
        }
    ]
