"""
`POST /api/v1/devices/reset/{request,confirm}` — couche HTTP.

Le service est teste ailleurs. Ce fichier verifie ce qui appartient a HTTP :
l absence d authentification, l uniformite de la reponse, les codes d erreur du
contrat, et les deux axes de quota.
"""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.core.adapters.notifications import InMemorySender
from apps.identity import views
from apps.identity.constants import OTP_MAX_ATTEMPTS, OTP_TTL_MINUTES
from apps.identity.models import User
from apps.identity.services.device_reset import DeviceResetService
from apps.identity.services.devices import DeviceBindingService

REQUEST_URL = "/api/v1/devices/reset/request"
CONFIRM_URL = "/api/v1/devices/reset/confirm"
PASSWORD = "Chataigne-Orageuse-2026"


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttle-reset-tests",
        }
    }
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def sender() -> InMemorySender:
    return InMemorySender()


@pytest.fixture
def service(sender) -> DeviceResetService:
    return DeviceResetService(binding=DeviceBindingService(lock=FakeDeviceLock()), sender=sender)


@pytest.fixture(autouse=True)
def wired(service, monkeypatch):
    monkeypatch.setattr(views, "build_device_reset_service", lambda: service)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


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
    return sender.emails_sent[-1]["body"].split("est ")[1][:6]


def body(**overrides) -> dict:
    payload = {"email": "supporter@example.test", "password": PASSWORD}
    payload.update(overrides)
    return payload


# ===========================================================================
# Demande
# ===========================================================================


def test_the_request_needs_no_authentication(client, fan):
    """
    Le coeur d ADR-S1-04 : exiger un jeton rendrait la route inutilisable par
    la seule personne qui en a besoin.
    """
    assert client.post(REQUEST_URL, body(), format="json").status_code == 200


def test_an_unknown_address_and_a_success_are_byte_identical_in_shape(client, fan):
    known = client.post(REQUEST_URL, body(), format="json")
    unknown = client.post(REQUEST_URL, body(email="jamais@example.test"), format="json")

    assert known.status_code == unknown.status_code == 200
    assert set(known.data) == set(unknown.data) == {"challenge_id", "expires_in_seconds"}
    assert known.data["expires_in_seconds"] == unknown.data["expires_in_seconds"]


def test_the_password_never_appears_in_the_response(client, fan):
    response = client.post(REQUEST_URL, body(), format="json")

    assert PASSWORD not in response.content.decode()


def test_the_code_never_appears_in_the_response(client, fan, sender):
    response = client.post(REQUEST_URL, body(), format="json")

    assert code_from(sender) not in response.content.decode()


def test_the_advertised_ttl_matches_the_plan(client, fan):
    response = client.post(REQUEST_URL, body(), format="json")

    assert response.data["expires_in_seconds"] == int(OTP_TTL_MINUTES) * 60


def test_a_missing_field_is_a_validation_error(client, fan):
    response = client.post(REQUEST_URL, {"email": "supporter@example.test"}, format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


# ===========================================================================
# Confirmation
# ===========================================================================


def test_a_valid_code_returns_204_and_no_token(client, fan, sender):
    opened = client.post(REQUEST_URL, body(), format="json")

    response = client.post(
        CONFIRM_URL,
        {"challenge_id": opened.data["challenge_id"], "code": code_from(sender)},
        format="json",
    )

    assert response.status_code == 204
    assert not response.data


def test_a_wrong_code_returns_otp_invalid(client, fan):
    opened = client.post(REQUEST_URL, body(), format="json")

    response = client.post(
        CONFIRM_URL, {"challenge_id": opened.data["challenge_id"], "code": "000000"}, format="json"
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "OTP_INVALID"


def test_an_unknown_challenge_returns_the_same_error(client, fan):
    """Un identifiant inconnu et un code faux sont indiscernables."""
    import uuid

    response = client.post(CONFIRM_URL, {"challenge_id": str(uuid.uuid4()), "code": "000000"}, format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "OTP_INVALID"


def test_the_sixth_attempt_returns_otp_max_attempts(client, fan):
    opened = client.post(REQUEST_URL, body(), format="json")
    payload = {"challenge_id": opened.data["challenge_id"], "code": "000000"}

    codes = [client.post(CONFIRM_URL, payload, format="json").status_code for _ in range(6)]

    assert codes[: OTP_MAX_ATTEMPTS - 1] == [400] * (OTP_MAX_ATTEMPTS - 1)
    assert codes[OTP_MAX_ATTEMPTS - 1] == 429
    last = client.post(CONFIRM_URL, payload, format="json")
    assert last.data["error"]["code"] == "OTP_INVALID", "defi consomme : retour au cas general"


def test_a_malformed_challenge_id_is_a_validation_error(client, fan):
    response = client.post(CONFIRM_URL, {"challenge_id": "pas-un-uuid", "code": "000000"}, format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


# ===========================================================================
# Quotas — deux axes
# ===========================================================================


def test_the_same_address_is_throttled_even_from_different_ips(client, fan, monkeypatch):
    """
    L axe qui protege la victime. Sans lui, mille adresses IP suffisent a noyer
    la boite d une personne ciblee, et le quota par origine n y peut rien.
    """
    from apps.identity.throttling import DeviceResetAccountRateThrottle

    monkeypatch.setattr(DeviceResetAccountRateThrottle, "THROTTLE_RATES", {"device_reset_account": "2/hour"})

    codes = [
        client.post(REQUEST_URL, body(), format="json", REMOTE_ADDR=f"203.0.113.{i}").status_code
        for i in range(1, 5)
    ]

    assert codes[:2] == [200, 200]
    assert codes[2] == 429, codes


def test_the_origin_axis_also_applies(client, fan, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"device_reset_request": "2/min"})

    codes = [client.post(REQUEST_URL, body(), format="json").status_code for _ in range(4)]

    assert codes[:2] == [200, 200]
    assert codes[2] == 429, codes


def test_the_confirm_endpoint_is_throttled_too(client, fan, monkeypatch):
    import uuid

    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"device_reset_confirm": "2/min"})
    payload = {"challenge_id": str(uuid.uuid4()), "code": "000000"}

    codes = [client.post(CONFIRM_URL, payload, format="json").status_code for _ in range(4)]

    assert codes[:2] == [400, 400]
    assert codes[2] == 429, codes
