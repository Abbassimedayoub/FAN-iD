from __future__ import annotations

import datetime

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.core.adapters.notifications import InMemorySender
from apps.identity import views
from apps.identity.constants import AUTH_LEVEL_PASSWORD, AUTH_LEVEL_STEP_UP
from apps.identity.models import Session, User
from apps.identity.services.authentication import AuthenticationService, LoginCommand
from apps.identity.services.devices import DeviceBindingService
from apps.identity.services.step_up import StepUpService

REQUEST_URL = "/api/v1/auth/step-up/request"
CONFIRM_URL = "/api/v1/auth/step-up/confirm"
PASSWORD = "Chataigne-Orageuse-2026"


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "step-up-http-tests",
        }
    }
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def sender() -> InMemorySender:
    return InMemorySender()


@pytest.fixture
def service(sender) -> StepUpService:
    return StepUpService(sender=sender)


@pytest.fixture(autouse=True)
def wired(service, monkeypatch):
    monkeypatch.setattr(views, "build_step_up_service", lambda: service)


@pytest.fixture
def auth() -> AuthenticationService:
    return AuthenticationService(binding=DeviceBindingService(lock=FakeDeviceLock()))


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def fan(db, roles) -> User:
    return User.objects.create_user(
        email="stepup-http@example.test",
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


def bearer(client: APIClient, access: str) -> None:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")


def code_from(sender: InMemorySender) -> str:
    body = sender.emails_sent[-1]["body"]
    return body.split("est ")[1][:6]


def test_request_requires_authentication(client):
    response = client.post(REQUEST_URL, {}, format="json")
    assert response.status_code == 401


def test_confirm_requires_authentication(client):
    response = client.post(
        CONFIRM_URL,
        {
            "challenge_id": "00000000-0000-0000-0000-000000000000",
            "code": "000000",
        },
        format="json",
    )
    assert response.status_code == 401


def test_request_returns_challenge(
    client,
    auth,
    fan,
    sender,
):
    opened = login(auth, fan)
    bearer(client, opened.pair.access)

    response = client.post(REQUEST_URL, {}, format="json")

    assert response.status_code == 200
    assert set(response.data) == {
        "challenge_id",
        "expires_in_seconds",
    }
    assert response.data["expires_in_seconds"] > 0
    assert len(code_from(sender)) == 6


def test_confirm_elevates_current_session(
    client,
    auth,
    fan,
    sender,
):
    opened = login(auth, fan)
    bearer(client, opened.pair.access)

    request_response = client.post(
        REQUEST_URL,
        {},
        format="json",
    )

    assert request_response.status_code == 200

    response = client.post(
        CONFIRM_URL,
        {
            "challenge_id": request_response.data["challenge_id"],
            "code": code_from(sender),
        },
        format="json",
    )

    assert response.status_code == 204

    session = Session.objects.get(pk=opened.pair.session.pk)
    assert session.auth_level == AUTH_LEVEL_STEP_UP


def test_same_access_token_observes_step_up_immediately(
    client,
    auth,
    fan,
    sender,
):
    opened = login(auth, fan)

    assert Session.objects.get(pk=opened.pair.session.pk).auth_level == AUTH_LEVEL_PASSWORD

    bearer(client, opened.pair.access)

    request_response = client.post(
        REQUEST_URL,
        {},
        format="json",
    )

    confirm_response = client.post(
        CONFIRM_URL,
        {
            "challenge_id": request_response.data["challenge_id"],
            "code": code_from(sender),
        },
        format="json",
    )

    assert confirm_response.status_code == 204

    # Aucun nouveau bearer n'est installe ici.
    # Le meme access token authentifie une nouvelle requete et
    # JWTAuthentication doit relire le niveau depuis Session.
    me_response = client.get("/api/v1/auth/me")

    assert me_response.status_code == 200

    session = Session.objects.get(pk=opened.pair.session.pk)
    assert session.auth_level == AUTH_LEVEL_STEP_UP


def test_wrong_code_is_rejected(
    client,
    auth,
    fan,
):
    opened = login(auth, fan)
    bearer(client, opened.pair.access)

    requested = client.post(REQUEST_URL, {}, format="json")

    response = client.post(
        CONFIRM_URL,
        {
            "challenge_id": requested.data["challenge_id"],
            "code": "000000",
        },
        format="json",
    )

    assert response.status_code == 400


def test_request_is_throttled(
    client,
    auth,
    fan,
    monkeypatch,
):
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {"step_up_request": "2/min"},
    )

    opened = login(auth, fan)
    bearer(client, opened.pair.access)

    codes = [client.post(REQUEST_URL, {}, format="json").status_code for _ in range(3)]

    assert codes == [200, 200, 429]


def test_confirm_is_throttled(
    client,
    auth,
    fan,
    monkeypatch,
):
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {"step_up_confirm": "2/min"},
    )

    opened = login(auth, fan)
    bearer(client, opened.pair.access)

    payload = {
        "challenge_id": "00000000-0000-0000-0000-000000000000",
        "code": "000000",
    }

    codes = [client.post(CONFIRM_URL, payload, format="json").status_code for _ in range(3)]

    assert codes[:2] == [400, 400]
    assert codes[2] == 429
