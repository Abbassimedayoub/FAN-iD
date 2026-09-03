from __future__ import annotations

import datetime
import re
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.core.adapters.notifications import InMemorySender
from apps.core.outbox.models import OutboxEvent
from apps.identity import authentication as auth_module
from apps.identity import consumers as identity_consumers
from apps.identity import tasks as identity_tasks
from apps.identity import views
from apps.identity.consumers import PasswordResetEmailConsumer
from apps.identity.events import (
    USER_PHONE_CHANGED,
    USER_PROFILE_UPDATED,
)
from apps.identity.models import User
from apps.identity.services.authentication import (
    AuthenticationService,
    LoginCommand,
)
from apps.identity.services.devices import DeviceBindingService
from apps.identity.services.phone_change import (
    PhoneChangeService,
)
from apps.identity.services.registration import (
    RegistrationCommand,
    RegistrationService,
)

PASSWORD = "Chataigne-Orageuse-2026"
REQUEST_URL = "/api/v1/auth/phone/change/request"
CONFIRM_URL = "/api/v1/auth/phone/change/confirm"
OLD_PHONE = "+33601020304"
NEW_PHONE = "+33 6 99 99 99 99"


@pytest.fixture(autouse=True)
def isolated_throttle_cache(
    settings,
):
    settings.CACHES = {
        "default": {
            "BACKEND": (
                "django.core.cache.backends."
                "locmem.LocMemCache"
            ),
            "LOCATION": (
                "phone-change-http-tests"
            ),
        }
    }
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def binding() -> DeviceBindingService:
    return DeviceBindingService(
        lock=FakeDeviceLock(),
    )


@pytest.fixture
def auth_service(
    binding,
) -> AuthenticationService:
    return AuthenticationService(
        binding=binding,
    )


@pytest.fixture(autouse=True)
def wired_authentication(
    binding,
    monkeypatch,
):
    monkeypatch.setattr(
        auth_module,
        "default_binding_service",
        lambda: binding,
    )


@pytest.fixture
def sender() -> InMemorySender:
    return InMemorySender()


@pytest.fixture(autouse=True)
def wired_phone_service(
    sender,
    monkeypatch,
):
    monkeypatch.setattr(
        views,
        "build_phone_change_service",
        lambda: PhoneChangeService(
            sender=sender,
        ),
    )


@pytest.fixture
def fan(
    db,
    roles,
) -> User:
    return User.objects.create_user(
        email="phone-change@example.test",
        password=PASSWORD,
        first_name="Ines",
        last_name="Bouzid",
        phone=OLD_PHONE,
        date_of_birth=datetime.date(
            1996,
            5,
            4,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


def authenticated_client(
    auth_service: AuthenticationService,
) -> APIClient:
    opened = auth_service.login(
        LoginCommand(
            email="phone-change@example.test",
            password=PASSWORD,
        )
    )

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=(
            f"Bearer {opened.pair.access}"
        )
    )
    return client


def otp_from(
    sender: InMemorySender,
) -> str:
    assert sender.emails_sent

    body = sender.emails_sent[-1][
        "body"
    ]

    match = re.search(
        r"\b([0-9]{6})\b",
        body,
    )

    assert match is not None
    return match.group(1)


@pytest.mark.django_db
def test_request_keeps_old_phone_until_confirmation(
    auth_service,
    fan,
    sender,
):
    client = authenticated_client(
        auth_service,
    )

    fan.refresh_from_db()
    initial_version = fan.version

    response = client.post(
        REQUEST_URL,
        {
            "phone": NEW_PHONE,
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert set(response.data) == {
        "challenge_id",
        "expires_in_seconds",
    }

    fan.refresh_from_db()

    assert fan.phone == OLD_PHONE
    assert fan.version == initial_version

    assert len(sender.emails_sent) == 1
    email = sender.emails_sent[0]

    assert email["to"] == fan.email
    assert NEW_PHONE in email["body"]


@pytest.mark.django_db
def test_wrong_code_never_replaces_old_phone(
    auth_service,
    fan,
    sender,
):
    client = authenticated_client(
        auth_service,
    )

    requested = client.post(
        REQUEST_URL,
        {
            "phone": NEW_PHONE,
        },
        format="json",
    )

    real_code = otp_from(
        sender,
    )
    wrong_code = (
        "000000"
        if real_code != "000000"
        else "000001"
    )

    response = client.post(
        CONFIRM_URL,
        {
            "challenge_id": (
                requested.data[
                    "challenge_id"
                ]
            ),
            "phone": NEW_PHONE,
            "code": wrong_code,
        },
        format="json",
    )

    assert response.status_code == 400
    assert (
        response.data["error"]["code"]
        == "OTP_INVALID"
    )

    fan.refresh_from_db()

    assert fan.phone == OLD_PHONE


@pytest.mark.django_db
def test_confirm_replaces_phone_atomically_and_emits_events(
    auth_service,
    fan,
    sender,
):
    client = authenticated_client(
        auth_service,
    )

    fan.refresh_from_db()
    initial_version = fan.version

    requested = client.post(
        REQUEST_URL,
        {
            "phone": NEW_PHONE,
        },
        format="json",
    )

    response = client.post(
        CONFIRM_URL,
        {
            "challenge_id": (
                requested.data[
                    "challenge_id"
                ]
            ),
            "phone": NEW_PHONE,
            "code": otp_from(
                sender,
            ),
        },
        format="json",
    )

    assert response.status_code == 200, response.data

    fan.refresh_from_db()

    assert fan.phone == NEW_PHONE
    assert fan.version == (
        initial_version + 1
    )
    assert response.data["phone"] == NEW_PHONE
    assert response["ETag"] == (
        f'"{initial_version + 1}"'
    )

    profile_event = (
        OutboxEvent.objects.filter(
            event_type=USER_PROFILE_UPDATED,
            aggregate_id=fan.pk,
        )
        .latest("occurred_at")
    )

    assert profile_event.payload == {
        "changed_fields": [
            "phone",
        ],
    }

    phone_event = (
        OutboxEvent.objects.filter(
            event_type=USER_PHONE_CHANGED,
            aggregate_id=fan.pk,
        )
        .latest("occurred_at")
    )

    assert phone_event.payload == {
        "first_record": False,
    }

    assert NEW_PHONE not in str(
        phone_event.payload,
    )


@pytest.mark.django_db
def test_otp_is_bound_to_requested_phone(
    auth_service,
    fan,
    sender,
):
    client = authenticated_client(
        auth_service,
    )

    requested = client.post(
        REQUEST_URL,
        {
            "phone": NEW_PHONE,
        },
        format="json",
    )

    response = client.post(
        CONFIRM_URL,
        {
            "challenge_id": (
                requested.data[
                    "challenge_id"
                ]
            ),
            "phone": "+33777777777",
            "code": otp_from(
                sender,
            ),
        },
        format="json",
    )

    assert response.status_code == 400
    assert (
        response.data["error"]["code"]
        == "OTP_INVALID"
    )

    fan.refresh_from_db()

    assert fan.phone == OLD_PHONE


@pytest.mark.django_db
def test_semantically_same_phone_is_refused(
    auth_service,
    fan,
    sender,
):
    client = authenticated_client(
        auth_service,
    )

    response = client.post(
        REQUEST_URL,
        {
            "phone": "+33 6 01 02 03 04",
        },
        format="json",
    )

    assert response.status_code == 400
    assert sender.emails_sent == []

    fan.refresh_from_db()
    assert fan.phone == OLD_PHONE


@pytest.mark.django_db
def test_confirmation_email_distinguishes_first_and_change(
    fan,
    monkeypatch,
):
    sender = InMemorySender()

    monkeypatch.setattr(
        identity_tasks,
        "build_notification_sender",
        lambda: sender,
    )

    identity_tasks.send_phone_changed_email.run(
        user_id=str(
            fan.pk,
        ),
        first_record=True,
    )

    assert len(
        sender.emails_sent,
    ) == 1

    assert "enregistré" in (
        sender.emails_sent[0][
            "subject"
        ]
    )

    sender.emails_sent.clear()

    identity_tasks.send_phone_changed_email.run(
        user_id=str(
            fan.pk,
        ),
        first_record=False,
    )

    assert len(
        sender.emails_sent,
    ) == 1

    assert "modifié" in (
        sender.emails_sent[0][
            "subject"
        ]
    )

    assert OLD_PHONE in (
        sender.emails_sent[0][
            "body"
        ]
    )


@pytest.mark.django_db
def test_identity_consumer_dispatches_phone_email(
    fan,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    delayed: list[
        dict[str, object]
    ] = []

    monkeypatch.setattr(
        identity_consumers
        .send_phone_changed_email,
        "delay",
        lambda **kwargs: delayed.append(
            kwargs,
        ),
    )

    event = SimpleNamespace(
        event_type=USER_PHONE_CHANGED,
        aggregate_id=fan.pk,
        payload={
            "first_record": False,
        },
    )

    consumer = PasswordResetEmailConsumer()

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        with transaction.atomic():
            consumer.handle(
                event,
            )

    assert delayed == [
        {
            "user_id": str(
                fan.pk,
            ),
            "first_record": False,
        }
    ]


@pytest.mark.django_db
def test_registration_with_phone_publishes_first_record_event(
    roles,
):
    user = RegistrationService.register(
        RegistrationCommand(
            email=(
                "first-phone-registration"
                "@example.test"
            ),
            password=PASSWORD,
            first_name="Premiere",
            last_name="Telephone",
            date_of_birth=datetime.date(
                1995,
                6,
                1,
            ),
            terms_accepted=True,
            phone="+33611112222",
        )
    )

    event = (
        OutboxEvent.objects.filter(
            event_type=USER_PHONE_CHANGED,
            aggregate_id=user.pk,
        )
        .latest("occurred_at")
    )

    assert event.payload == {
        "first_record": True,
    }

    assert "+33611112222" not in str(
        event.payload,
    )
