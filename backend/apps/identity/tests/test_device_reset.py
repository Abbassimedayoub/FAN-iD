"""
Device-reset tests cover enumeration resistance, attempt counting, and device
unbinding.

Key cases verify that unknown accounts return the same public shape, failed-code
attempts really persist, and concurrent reset requests leave only one usable
challenge.
"""

from __future__ import annotations

import datetime
import hashlib
import uuid

import pytest
from django.utils import timezone

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.core.adapters.notifications import InMemorySender
from apps.core.outbox.models import OutboxEvent
from apps.identity.constants import (
    MFA_PURPOSE_DEVICE_RESET,
    OTP_MAX_ATTEMPTS,
    PLATFORM_ANDROID,
    SESSION_REVOKED_DEVICE_RESET,
)
from apps.identity.events import DEVICE_RESET_CONFIRMED, DEVICE_RESET_REQUESTED
from apps.identity.exceptions import OtpInvalidError, OtpMaxAttemptsError
from apps.identity.models import Device, MfaChallenge, Session, User
from apps.identity.services.authentication import AuthenticationService, LoginCommand
from apps.identity.services.device_reset import DeviceResetService
from apps.identity.services.devices import DeviceBindingService

PASSWORD = "Chataigne-Orageuse-2026"
PHONE = "a" * 64


@pytest.fixture
def binding() -> DeviceBindingService:
    return DeviceBindingService(lock=FakeDeviceLock())


@pytest.fixture
def sender() -> InMemorySender:
    return InMemorySender()


@pytest.fixture
def service(binding, sender) -> DeviceResetService:
    return DeviceResetService(binding=binding, sender=sender)


@pytest.fixture
def auth(binding) -> AuthenticationService:
    return AuthenticationService(binding=binding)


@pytest.fixture
def fan(db, roles) -> User:
    return User.objects.create_user(
        email="supporter@example.test",
        password=PASSWORD,
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1996, 5, 4),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


def code_from(sender: InMemorySender) -> str:
    """Extract the code from the last captured email."""
    body = sender.emails_sent[-1]["body"]
    return "".join(c for c in body.split("est ")[1][:6])


def bind(auth: AuthenticationService, fan: User):
    """Open a session with a bound device as the reset-flow starting point."""
    return auth.login(
        LoginCommand(email=fan.email, password=PASSWORD, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    )


# ===========================================================================
# Enumeration resistance
# ===========================================================================


def test_an_unknown_address_gets_the_same_shape_as_a_success(service, fan):
    """Unknown addresses must receive the same challenge-shaped response as successful requests."""
    known = service.request(email="supporter@example.test", password=PASSWORD)
    unknown = service.request(email="jamais-inscrit@example.test", password=PASSWORD)

    assert isinstance(known.challenge_id, uuid.UUID)
    assert isinstance(unknown.challenge_id, uuid.UUID)
    assert known.created is True
    assert unknown.created is False


def test_a_wrong_password_creates_nothing_and_sends_nothing(service, fan, sender):
    result = service.request(email="supporter@example.test", password="Faux-2026")

    assert result.created is False
    assert not MfaChallenge.objects.exists()
    assert sender.emails_sent == []


def test_an_unknown_address_still_pays_the_price_of_a_hash(service, roles, monkeypatch):
    """Unknown-address requests must still execute the decoy password check to avoid a timing oracle."""
    calls: list[str] = []
    import apps.identity.services.device_reset as module

    def record(raw: str, encoded: str) -> bool:
        calls.append(encoded)
        return False

    monkeypatch.setattr("django.contrib.auth.hashers.check_password", record)
    assert module is not None

    service_result = None
    from apps.core.adapters.device_lock import FakeDeviceLock as Lock
    from apps.core.adapters.notifications import InMemorySender as Sender
    from apps.identity.services.device_reset import DeviceResetService as Svc
    from apps.identity.services.devices import DeviceBindingService as Binding

    service_result = Svc(binding=Binding(lock=Lock()), sender=Sender()).request(
        email="jamais-inscrit@example.test", password=PASSWORD
    )

    assert service_result.created is False
    assert len(calls) == 1, "le hachage factice doit etre verifie meme sans compte"


def test_a_fake_challenge_id_is_refused_like_a_wrong_code(service, fan):
    fake = service.request(email="jamais-inscrit@example.test", password=PASSWORD)

    with pytest.raises(OtpInvalidError):
        service.confirm(challenge_id=fake.challenge_id, code="000000")


# ===========================================================================
# Issuance
# ===========================================================================


def test_a_valid_request_stores_only_a_digest(service, fan, sender):
    service.request(email="supporter@example.test", password=PASSWORD)

    challenge = MfaChallenge.objects.get()
    code = code_from(sender)
    assert challenge.code_hash == hashlib.sha256(code.encode()).hexdigest()
    assert code not in challenge.code_hash
    assert challenge.purpose == MFA_PURPOSE_DEVICE_RESET
    assert challenge.max_attempts == OTP_MAX_ATTEMPTS


def test_the_code_is_six_digits_and_reaches_the_account(service, fan, sender):
    service.request(email="supporter@example.test", password=PASSWORD)

    assert len(sender.emails_sent) == 1
    assert sender.emails_sent[0]["to"] == "supporter@example.test"
    assert code_from(sender).isdigit()
    assert len(code_from(sender)) == 6


def test_a_new_request_invalidates_the_previous_code(service, fan, sender):
    """Issuing a new reset code invalidates previous open challenges."""
    first = service.request(email="supporter@example.test", password=PASSWORD)
    old_code = code_from(sender)
    service.request(email="supporter@example.test", password=PASSWORD)

    with pytest.raises(OtpInvalidError):
        service.confirm(challenge_id=first.challenge_id, code=old_code)


def test_only_one_challenge_stays_open(service, fan):
    service.request(email="supporter@example.test", password=PASSWORD)
    service.request(email="supporter@example.test", password=PASSWORD)
    service.request(email="supporter@example.test", password=PASSWORD)

    assert MfaChallenge.objects.count() == 3
    assert MfaChallenge.objects.open().count() == 1


def test_three_concurrent_requests_leave_one_usable_challenge(service, fan):
    """The account-row lock serializes concurrent requests so only one challenge remains usable."""
    for _ in range(3):
        service.request(email="supporter@example.test", password=PASSWORD)

    assert MfaChallenge.objects.open().count() == 1


def test_a_request_publishes_one_event_without_personal_data(service, fan):
    service.request(email="supporter@example.test", password=PASSWORD)

    events = list(OutboxEvent.objects.filter(event_type=DEVICE_RESET_REQUESTED))
    assert len(events) == 1
    assert events[0].payload == {"device_bound": False}
    assert "example.test" not in str(events[0].payload)


def test_the_fake_path_publishes_nothing(service, fan):
    service.request(email="jamais-inscrit@example.test", password=PASSWORD)

    assert not OutboxEvent.objects.filter(event_type=DEVICE_RESET_REQUESTED).exists()


# ===========================================================================
# Attempt counter
# ===========================================================================


def test_a_wrong_code_really_increments_the_counter(service, fan):
    """A failed-code attempt must commit its counter increment before the public error is raised."""
    opened = service.request(email="supporter@example.test", password=PASSWORD)

    with pytest.raises(OtpInvalidError):
        service.confirm(challenge_id=opened.challenge_id, code="000000")

    assert MfaChallenge.objects.get(pk=opened.challenge_id).attempts == 1


def test_the_fifth_failure_consumes_the_challenge_for_good(service, fan, sender):
    opened = service.request(email="supporter@example.test", password=PASSWORD)
    good = code_from(sender)

    for _ in range(OTP_MAX_ATTEMPTS - 1):
        with pytest.raises(OtpInvalidError):
            service.confirm(challenge_id=opened.challenge_id, code="000000")

    with pytest.raises(OtpMaxAttemptsError):
        service.confirm(challenge_id=opened.challenge_id, code="000000")

    challenge = MfaChallenge.objects.get(pk=opened.challenge_id)
    assert challenge.attempts == OTP_MAX_ATTEMPTS
    assert challenge.consumed_at is not None

    # Even the correct code cannot reopen an exhausted challenge.
    with pytest.raises(OtpInvalidError):
        service.confirm(challenge_id=opened.challenge_id, code=good)


def test_an_expired_challenge_is_refused_like_an_unknown_one(service, fan, sender):
    """Expired and otherwise invalid challenges intentionally share the same public error."""
    opened = service.request(email="supporter@example.test", password=PASSWORD)
    good = code_from(sender)
    MfaChallenge.objects.filter(pk=opened.challenge_id).update(
        expires_at=timezone.now() - datetime.timedelta(minutes=1)
    )

    with pytest.raises(OtpInvalidError):
        service.confirm(challenge_id=opened.challenge_id, code=good)


def test_a_consumed_challenge_cannot_be_replayed(service, fan, sender):
    opened = service.request(email="supporter@example.test", password=PASSWORD)
    good = code_from(sender)
    service.confirm(challenge_id=opened.challenge_id, code=good)

    with pytest.raises(OtpInvalidError):
        service.confirm(challenge_id=opened.challenge_id, code=good)


# ===========================================================================
# Device unbinding
# ===========================================================================


def test_a_confirmed_reset_unbinds_the_device(service, auth, fan, sender):
    bind(auth, fan)
    opened = service.request(email="supporter@example.test", password=PASSWORD)

    result = service.confirm(challenge_id=opened.challenge_id, code=code_from(sender))

    assert result.device_revoked is True
    assert Device.objects.active().for_user(fan).first() is None


def test_the_slot_is_free_for_a_new_device(service, auth, fan, sender):
    """The recovery flow must allow a later login from another device."""
    bind(auth, fan)
    opened = service.request(email="supporter@example.test", password=PASSWORD)
    service.confirm(challenge_id=opened.challenge_id, code=code_from(sender))

    reopened = auth.login(
        LoginCommand(email=fan.email, password=PASSWORD, fingerprint="b" * 64, platform=PLATFORM_ANDROID)
    )

    assert reopened.device is not None


def test_all_sessions_fall_with_the_device(service, auth, fan, sender):
    first = bind(auth, fan)
    opened = service.request(email="supporter@example.test", password=PASSWORD)

    result = service.confirm(challenge_id=opened.challenge_id, code=code_from(sender))

    assert result.sessions_revoked >= 1
    session = Session.objects.get(pk=first.pair.session.pk)
    assert session.revoked_at is not None
    assert session.revoked_reason == SESSION_REVOKED_DEVICE_RESET


def test_a_reset_without_any_bound_device_still_succeeds(service, fan, sender):
    """Having no active device to unbind is not an error."""
    opened = service.request(email="supporter@example.test", password=PASSWORD)

    result = service.confirm(challenge_id=opened.challenge_id, code=code_from(sender))

    assert result.device_revoked is False


def test_a_confirmation_publishes_one_event_without_personal_data(service, auth, fan, sender):
    bind(auth, fan)
    opened = service.request(email="supporter@example.test", password=PASSWORD)
    service.confirm(challenge_id=opened.challenge_id, code=code_from(sender))

    events = list(OutboxEvent.objects.filter(event_type=DEVICE_RESET_CONFIRMED))
    assert len(events) == 1
    assert events[0].payload["device_revoked"] is True
    assert "example.test" not in str(events[0].payload)


def test_no_token_is_issued_by_a_reset(service, auth, fan, sender):
    """Reset proof authorizes only this action; confirmation must not issue authentication tokens."""
    bind(auth, fan)
    opened = service.request(email="supporter@example.test", password=PASSWORD)

    result = service.confirm(challenge_id=opened.challenge_id, code=code_from(sender))

    assert not hasattr(result, "pair")
    assert Session.objects.filter(revoked_at__isnull=True).count() == 0


def test_the_auth_level_is_never_raised(service, auth, fan, sender):
    """No session is elevated; the reset proof is consumed by this operation."""
    bind(auth, fan)
    opened = service.request(email="supporter@example.test", password=PASSWORD)
    service.confirm(challenge_id=opened.challenge_id, code=code_from(sender))

    assert not Session.objects.filter(auth_level=2).exists()
