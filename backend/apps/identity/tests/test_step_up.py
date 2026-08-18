from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.core.adapters.notifications import InMemorySender
from apps.identity.constants import (
    AUTH_LEVEL_PASSWORD,
    AUTH_LEVEL_STEP_UP,
    MFA_PURPOSE_STEP_UP,
    OTP_MAX_ATTEMPTS,
)
from apps.identity.exceptions import OtpInvalidError, OtpMaxAttemptsError
from apps.identity.models import MfaChallenge, Session, User
from apps.identity.services.authentication import AuthenticationService, LoginCommand
from apps.identity.services.devices import DeviceBindingService
from apps.identity.services.step_up import StepUpService

PASSWORD = "Chataigne-Orageuse-2026"


@pytest.fixture
def sender() -> InMemorySender:
    return InMemorySender()


@pytest.fixture
def service(sender) -> StepUpService:
    return StepUpService(sender=sender)


@pytest.fixture
def auth() -> AuthenticationService:
    return AuthenticationService(binding=DeviceBindingService(lock=FakeDeviceLock()))


@pytest.fixture
def fan(db, roles) -> User:
    return User.objects.create_user(
        email="stepup@example.test",
        password=PASSWORD,
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1996, 5, 4),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


def login(auth: AuthenticationService, fan: User):
    return auth.login(
        LoginCommand(
            email=fan.email,
            password=PASSWORD,
        )
    )


def code_from(sender: InMemorySender) -> str:
    body = sender.emails_sent[-1]["body"]
    return body.split("est ")[1][:6]


def test_request_creates_one_step_up_challenge(
    service,
    auth,
    fan,
    sender,
):
    opened = login(auth, fan)

    result = service.request(
        user=fan,
        session_id=opened.pair.session.pk,
    )

    challenge = MfaChallenge.objects.get(pk=result.challenge_id)

    assert challenge.user_id == fan.pk
    assert challenge.purpose == MFA_PURPOSE_STEP_UP
    assert challenge.consumed_at is None
    assert len(code_from(sender)) == 6
    assert code_from(sender).isdigit()


def test_new_request_invalidates_previous_challenge(
    service,
    auth,
    fan,
):
    opened = login(auth, fan)

    first = service.request(
        user=fan,
        session_id=opened.pair.session.pk,
    )

    service.request(
        user=fan,
        session_id=opened.pair.session.pk,
    )

    first_challenge = MfaChallenge.objects.get(pk=first.challenge_id)

    assert first_challenge.consumed_at is not None
    assert (
        MfaChallenge.objects.for_purpose(
            fan,
            MFA_PURPOSE_STEP_UP,
        )
        .open()
        .count()
        == 1
    )


def test_wrong_code_really_increments_attempts(
    service,
    auth,
    fan,
):
    opened = login(auth, fan)

    challenge = service.request(
        user=fan,
        session_id=opened.pair.session.pk,
    )

    with pytest.raises(OtpInvalidError):
        service.confirm(
            user=fan,
            session_id=opened.pair.session.pk,
            challenge_id=challenge.challenge_id,
            code="000000",
        )

    assert MfaChallenge.objects.get(pk=challenge.challenge_id).attempts == 1


def test_fifth_wrong_code_consumes_challenge(
    service,
    auth,
    fan,
):
    opened = login(auth, fan)

    challenge = service.request(
        user=fan,
        session_id=opened.pair.session.pk,
    )

    for _ in range(OTP_MAX_ATTEMPTS - 1):
        with pytest.raises(OtpInvalidError):
            service.confirm(
                user=fan,
                session_id=opened.pair.session.pk,
                challenge_id=challenge.challenge_id,
                code="000000",
            )

    with pytest.raises(OtpMaxAttemptsError):
        service.confirm(
            user=fan,
            session_id=opened.pair.session.pk,
            challenge_id=challenge.challenge_id,
            code="000000",
        )

    stored = MfaChallenge.objects.get(pk=challenge.challenge_id)

    assert stored.attempts == OTP_MAX_ATTEMPTS
    assert stored.consumed_at is not None


def test_valid_code_elevates_only_current_session(
    service,
    auth,
    fan,
    sender,
):
    first = login(auth, fan)
    second = login(auth, fan)

    assert first.pair.session.auth_level == AUTH_LEVEL_PASSWORD
    assert second.pair.session.auth_level == AUTH_LEVEL_PASSWORD

    challenge = service.request(
        user=fan,
        session_id=first.pair.session.pk,
    )

    service.confirm(
        user=fan,
        session_id=first.pair.session.pk,
        challenge_id=challenge.challenge_id,
        code=code_from(sender),
    )

    first_session = Session.objects.get(pk=first.pair.session.pk)
    second_session = Session.objects.get(pk=second.pair.session.pk)

    assert first_session.auth_level == AUTH_LEVEL_STEP_UP
    assert second_session.auth_level == AUTH_LEVEL_PASSWORD


def test_challenge_is_bound_to_the_requesting_session(
    service,
    auth,
    fan,
    sender,
):
    first = login(auth, fan)
    second = login(auth, fan)

    challenge = service.request(
        user=fan,
        session_id=first.pair.session.pk,
    )

    code = code_from(sender)

    with pytest.raises(OtpInvalidError):
        service.confirm(
            user=fan,
            session_id=second.pair.session.pk,
            challenge_id=challenge.challenge_id,
            code=code,
        )

    assert Session.objects.get(pk=second.pair.session.pk).auth_level == AUTH_LEVEL_PASSWORD


def test_challenge_cannot_be_used_by_another_user(
    service,
    auth,
    fan,
    sender,
    roles,
):
    opened = login(auth, fan)

    other = User.objects.create_user(
        email="other-stepup@example.test",
        password=PASSWORD,
        first_name="Autre",
        last_name="Compte",
        date_of_birth=datetime.date(1995, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )
    other_login = login(auth, other)

    challenge = service.request(
        user=fan,
        session_id=opened.pair.session.pk,
    )

    with pytest.raises(OtpInvalidError):
        service.confirm(
            user=other,
            session_id=other_login.pair.session.pk,
            challenge_id=challenge.challenge_id,
            code=code_from(sender),
        )

    assert Session.objects.get(pk=other_login.pair.session.pk).auth_level == AUTH_LEVEL_PASSWORD
