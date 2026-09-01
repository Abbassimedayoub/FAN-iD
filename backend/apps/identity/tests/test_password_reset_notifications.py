from __future__ import annotations

import datetime
import hashlib
import uuid
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.adapters.notifications import InMemorySender
from apps.identity import consumers, tasks
from apps.identity.constants import MFA_PURPOSE_PASSWORD_RESET, PASSWORD_RESET_TTL_MINUTES
from apps.identity.consumers import PasswordResetEmailConsumer
from apps.identity.events import PASSWORD_RESET_COMPLETED, PASSWORD_RESET_REQUESTED
from apps.identity.models import MfaChallenge
from apps.identity.services.password_reset import derive_password_reset_code

User = get_user_model()

pytestmark = pytest.mark.django_db


def make_user(
    roles,
):
    return User.objects.create_user(
        email=(f"{uuid.uuid4()}" "@example.test"),
        password=("Chataigne-Orageuse-2026"),
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(
            1990,
            3,
            12,
        ),
        terms_accepted_at=(timezone.now()),
        role=roles["ADMIN"],
    )


def make_challenge(
    user,
):
    challenge_id = uuid.uuid4()

    code = derive_password_reset_code(challenge_id)

    return MfaChallenge.objects.create(
        id=challenge_id,
        user=user,
        purpose=(MFA_PURPOSE_PASSWORD_RESET),
        code_hash=(hashlib.sha256(code.encode("utf-8")).hexdigest()),
        expires_at=(timezone.now() + datetime.timedelta(minutes=int(PASSWORD_RESET_TTL_MINUTES))),
    )


def test_reset_email_contains_magic_link_and_backup_code(
    monkeypatch,
    roles,
):
    user = make_user(roles)

    challenge = make_challenge(user)

    sender = InMemorySender()

    monkeypatch.setattr(
        tasks,
        "build_notification_sender",
        lambda: sender,
    )

    result = tasks.send_password_reset_email.run(
        user_id=str(user.pk),
        challenge_id=str(challenge.pk),
    )

    assert result["sent"] is True

    assert len(sender.emails_sent) == 1

    email = sender.emails_sent[0]

    code = derive_password_reset_code(challenge.pk)

    assert email["to"] == user.email

    assert code in email["body"]

    assert "/password-reset?token=" in email["body"]

    assert "15 minutes" in email["body"]


def test_password_changed_security_email(
    monkeypatch,
    roles,
):
    user = make_user(roles)

    sender = InMemorySender()

    monkeypatch.setattr(
        tasks,
        "build_notification_sender",
        lambda: sender,
    )

    result = tasks.send_password_changed_email.run(
        user_id=str(user.pk),
    )

    assert result["sent"] is True

    assert len(sender.emails_sent) == 1

    email = sender.emails_sent[0]

    assert email["to"] == user.email

    assert "modifié" in email["subject"]

    assert "sessions" in email["body"].lower()


def test_request_consumer_defers_reset_email(
    monkeypatch,
):
    user_id = uuid.uuid4()

    challenge_id = uuid.uuid4()

    calls = []

    monkeypatch.setattr(
        PasswordResetEmailConsumer,
        "defer",
        staticmethod(lambda callback: callback()),
    )

    monkeypatch.setattr(
        consumers.send_password_reset_email,
        "delay",
        lambda **kwargs: (calls.append(kwargs)),
    )

    event = SimpleNamespace(
        aggregate_id=user_id,
        event_type=(PASSWORD_RESET_REQUESTED),
        payload={"challenge_id": str(challenge_id)},
    )

    PasswordResetEmailConsumer().handle(event)

    assert calls == [
        {
            "user_id": str(user_id),
            "challenge_id": str(challenge_id),
        }
    ]


def test_completed_consumer_defers_security_email(
    monkeypatch,
):
    user_id = uuid.uuid4()

    calls = []

    monkeypatch.setattr(
        PasswordResetEmailConsumer,
        "defer",
        staticmethod(lambda callback: callback()),
    )

    monkeypatch.setattr(
        consumers.send_password_changed_email,
        "delay",
        lambda **kwargs: (calls.append(kwargs)),
    )

    event = SimpleNamespace(
        aggregate_id=user_id,
        event_type=(PASSWORD_RESET_COMPLETED),
        payload={"sessions_revoked": 2},
    )

    PasswordResetEmailConsumer().handle(event)

    assert calls == [
        {
            "user_id": str(user_id),
        }
    ]
