"""
Contrat d'alimentation des métriques métier d'identity.

Les assertions portent sur des DELTAS et jamais sur une valeur absolue :
le registre Prometheus par défaut est global au processus de test.
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from django.utils import timezone
from prometheus_client import REGISTRY

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.core.adapters.notifications import InMemorySender
from apps.core.observability.metrics import AUTHZ_ROLE_ANONYMOUS
from apps.identity.constants import OTP_MAX_ATTEMPTS, PLATFORM_ANDROID
from apps.identity.exceptions import (
    DeviceLockedError,
    DeviceMismatchError,
    InvalidCredentialsError,
    OtpInvalidError,
    OtpMaxAttemptsError,
)
from apps.identity.models import User
from apps.identity.services.authentication import AuthenticationService, LoginCommand, RefreshCommand
from apps.identity.services.device_reset import DeviceResetService
from apps.identity.services.devices import DeviceBindingService
from apps.identity.tokens import TokenInvalidError, TokenReuseDetectedError

PASSWORD = "Chataigne-Orageuse-2026"
PHONE = "a" * 64
TABLET = "b" * 64


def metric(name: str, labels: dict[str, str] | None = None) -> float:
    value = REGISTRY.get_sample_value(name, labels or {})
    return float(value or 0.0)


def make_user(roles, email: str = "supporter@example.test") -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1996, 5, 4),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


@pytest.fixture
def binding() -> DeviceBindingService:
    return DeviceBindingService(lock=FakeDeviceLock())


@pytest.fixture
def auth(binding) -> AuthenticationService:
    return AuthenticationService(binding=binding)


@pytest.fixture
def sender() -> InMemorySender:
    return InMemorySender()


@pytest.fixture
def reset(binding, sender) -> DeviceResetService:
    return DeviceResetService(binding=binding, sender=sender)


@pytest.fixture
def fan(db, roles) -> User:
    return make_user(roles)


def login_delta(result: str) -> float:
    return metric("fanid_auth_login_total", {"result": result})


def refresh_delta(result: str) -> float:
    return metric("fanid_auth_token_refresh_total", {"result": result})


def reset_delta(result: str) -> float:
    return metric("fanid_device_reset_total", {"result": result})


def test_login_success_increments_success(auth, fan):
    before = login_delta("success")

    auth.login(LoginCommand(email=fan.email, password=PASSWORD))

    assert login_delta("success") - before == 1


def test_unknown_email_and_wrong_password_share_bad_credentials(auth, fan):
    before = login_delta("bad_credentials")

    with pytest.raises(InvalidCredentialsError):
        auth.login(LoginCommand(email="jamais-inscrit@example.test", password=PASSWORD))

    middle = login_delta("bad_credentials")
    assert middle - before == 1

    with pytest.raises(InvalidCredentialsError):
        auth.login(LoginCommand(email=fan.email, password="Faux-Mot-De-Passe-2026"))

    assert login_delta("bad_credentials") - middle == 1


def test_inactive_login_increments_inactive(auth, fan):
    fan.is_active = False
    fan.save(update_fields=["is_active"])
    before = login_delta("inactive")

    with pytest.raises(InvalidCredentialsError):
        auth.login(LoginCommand(email=fan.email, password=PASSWORD))

    assert login_delta("inactive") - before == 1


def test_locked_device_increments_device_locked(auth, binding, fan):
    auth.login(
        LoginCommand(
            email=fan.email,
            password=PASSWORD,
            fingerprint=PHONE,
            platform=PLATFORM_ANDROID,
        )
    )
    before = login_delta("device_locked")

    with pytest.raises(DeviceLockedError):
        auth.login(
            LoginCommand(
                email=fan.email,
                password=PASSWORD,
                fingerprint=TABLET,
                platform=PLATFORM_ANDROID,
            )
        )

    assert login_delta("device_locked") - before == 1


def test_refresh_success_increments_success(auth, fan):
    opened = auth.login(LoginCommand(email=fan.email, password=PASSWORD))
    before = refresh_delta("success")

    auth.refresh(RefreshCommand(refresh=opened.pair.refresh))

    assert refresh_delta("success") - before == 1


def test_refresh_reuse_increments_both_reuse_metrics(auth, fan):
    opened = auth.login(LoginCommand(email=fan.email, password=PASSWORD))
    auth.refresh(RefreshCommand(refresh=opened.pair.refresh))

    refresh_before = refresh_delta("reuse_detected")
    reuse_before = metric("fanid_auth_token_reuse_detected_total")

    with pytest.raises(TokenReuseDetectedError):
        auth.refresh(RefreshCommand(refresh=opened.pair.refresh))

    assert refresh_delta("reuse_detected") - refresh_before == 1
    assert metric("fanid_auth_token_reuse_detected_total") - reuse_before == 1


def test_refresh_device_mismatch_increments_device_mismatch(auth, fan):
    opened = auth.login(
        LoginCommand(
            email=fan.email,
            password=PASSWORD,
            fingerprint=PHONE,
            platform=PLATFORM_ANDROID,
        )
    )
    before = refresh_delta("device_mismatch")

    with pytest.raises(DeviceMismatchError):
        auth.refresh(RefreshCommand(refresh=opened.pair.refresh, fingerprint=TABLET))

    assert refresh_delta("device_mismatch") - before == 1


def test_device_reset_success_increments_success(reset, fan, sender):
    opened = reset.request(email=fan.email, password=PASSWORD)
    code = "".join(c for c in sender.emails_sent[-1]["body"].split("est ")[1][:6])
    before = reset_delta("success")

    reset.confirm(challenge_id=opened.challenge_id, code=code)

    assert reset_delta("success") - before == 1


def test_device_reset_invalid_increments_invalid(reset, fan):
    opened = reset.request(email=fan.email, password=PASSWORD)
    before = reset_delta("invalid")

    with pytest.raises(OtpInvalidError):
        reset.confirm(challenge_id=opened.challenge_id, code="000000")

    assert reset_delta("invalid") - before == 1


def test_device_reset_exhausted_increments_exhausted(reset, fan):
    opened = reset.request(email=fan.email, password=PASSWORD)

    for _ in range(OTP_MAX_ATTEMPTS - 1):
        with pytest.raises(OtpInvalidError):
            reset.confirm(challenge_id=opened.challenge_id, code="000000")

    before = reset_delta("exhausted")

    with pytest.raises(OtpMaxAttemptsError):
        reset.confirm(challenge_id=opened.challenge_id, code="000000")

    assert reset_delta("exhausted") - before == 1


def test_fake_device_reset_request_does_not_increment_confirmation_metrics(reset, db):
    labels = ("success", "invalid", "exhausted")
    before = {label: reset_delta(label) for label in labels}

    result = reset.request(email="jamais-inscrit@example.test", password=PASSWORD)

    assert result.created is False
    assert {label: reset_delta(label) for label in labels} == before


def test_anonymous_role_literal_is_closed():
    assert AUTHZ_ROLE_ANONYMOUS == "anonymous"


def test_refresh_invalid_increments_invalid(auth):
    before = refresh_delta("invalid")

    with pytest.raises(TokenInvalidError):
        auth.refresh(RefreshCommand(refresh="not-a-token"))

    assert refresh_delta("invalid") - before == 1


def test_refresh_expired_increments_expired(auth, fan):
    from apps.identity.tokens import TokenType, encode_token

    expired, _, _ = encode_token(
        token_type=TokenType.REFRESH,
        subject=fan.pk,
        lifetime=datetime.timedelta(minutes=1),
        claims={"family": "11111111-1111-4111-8111-111111111111"},
        issued_at=timezone.now() - datetime.timedelta(minutes=2),
    )

    before = refresh_delta("expired")

    from apps.identity.tokens import TokenExpiredError

    with pytest.raises(TokenExpiredError):
        auth.refresh(RefreshCommand(refresh=expired))

    assert refresh_delta("expired") - before == 1


def test_authz_denied_increments_for_real_role():
    from types import SimpleNamespace

    from rest_framework.test import APIRequestFactory

    from apps.identity.authz import Action
    from apps.identity.constants import ROLE_IDS
    from apps.identity.permissions import ActionPermission

    factory = APIRequestFactory()
    request: Any = factory.get("/whatever")
    request.user = SimpleNamespace(
        pk=None,
        is_authenticated=True,
        is_active=True,
        role_id=ROLE_IDS["FAN"],
        anonymized_at=None,
    )
    request.auth_level = 1

    view = SimpleNamespace(
        required_action=Action.ORGANIZER_APPROVE,
        action=None,
        policy_actions={},
    )

    before = metric(
        "fanid_authz_denied_total",
        {"action": str(Action.ORGANIZER_APPROVE), "role": "FAN"},
    )

    assert ActionPermission().has_permission(request, view) is False

    assert (
        metric(
            "fanid_authz_denied_total",
            {"action": str(Action.ORGANIZER_APPROVE), "role": "FAN"},
        )
        - before
        == 1
    )


def test_authz_denied_increments_for_anonymous_role():
    from types import SimpleNamespace

    from rest_framework.test import APIRequestFactory

    from apps.identity.authz import Action
    from apps.identity.permissions import BasePolicyPermission

    factory = APIRequestFactory()
    request: Any = factory.get("/whatever")
    request.user = SimpleNamespace(is_authenticated=False)

    view = SimpleNamespace(required_action=Action.DEVICE_LIST_SELF)

    before = metric(
        "fanid_authz_denied_total",
        {
            "action": str(Action.DEVICE_LIST_SELF),
            "role": AUTHZ_ROLE_ANONYMOUS,
        },
    )

    assert BasePolicyPermission().has_permission(request, view) is False

    assert (
        metric(
            "fanid_authz_denied_total",
            {
                "action": str(Action.DEVICE_LIST_SELF),
                "role": AUTHZ_ROLE_ANONYMOUS,
            },
        )
        - before
        == 1
    )
