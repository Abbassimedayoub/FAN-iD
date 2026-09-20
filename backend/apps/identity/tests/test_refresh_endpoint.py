"""HTTP tests for refresh-token source selection and response transport."""

from __future__ import annotations

import datetime

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.identity import views
from apps.identity.constants import PLATFORM_ANDROID
from apps.identity.models import User
from apps.identity.services.authentication import AuthenticationService, LoginCommand
from apps.identity.services.devices import DeviceBindingService

URL = "/api/v1/auth/token/refresh"
PASSWORD = "Chataigne-Orageuse-2026"
PHONE = "a" * 64
TABLET = "b" * 64


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    """Use a test-local throttle counter, matching the login endpoint tests."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttle-refresh-tests",
        }
    }
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def binding() -> DeviceBindingService:
    return DeviceBindingService(lock=FakeDeviceLock())


@pytest.fixture
def service(binding) -> AuthenticationService:
    return AuthenticationService(binding=binding)


@pytest.fixture(autouse=True)
def in_memory_lock(service, monkeypatch):
    monkeypatch.setattr(views, "build_authentication_service", lambda: service)


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


@pytest.fixture
def opened(service, fan):
    """A browser-style session opened without a bound device."""
    return service.login(LoginCommand(email="supporter@example.test", password=PASSWORD))


@pytest.fixture
def opened_on_phone(service, fan):
    return service.login(
        LoginCommand(
            email="supporter@example.test",
            password=PASSWORD,
            fingerprint=PHONE,
            platform=PLATFORM_ANDROID,
        )
    )


# ===========================================================================
# Read only the source declared by the client
# ===========================================================================


def test_a_web_client_reads_the_cookie_and_receives_a_new_one(client, opened, settings):
    client.cookies[settings.REFRESH_COOKIE_NAME] = opened.pair.refresh

    response = client.post(URL, {"client": "web"}, format="json")

    assert response.status_code == 200, response.data
    assert "refresh" not in response.data
    assert "access" in response.data

    cookie = response.cookies[settings.REFRESH_COOKIE_NAME]
    assert cookie["httponly"] is True
    assert cookie.value != opened.pair.refresh, "le cookie doit porter le NOUVEAU jeton"


def test_a_mobile_client_reads_the_body_and_receives_the_refresh_in_the_body(client, opened, settings):
    response = client.post(URL, {"client": "mobile", "refresh": opened.pair.refresh}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["refresh"]
    assert response.data["refresh"] != opened.pair.refresh
    assert settings.REFRESH_COOKIE_NAME not in response.cookies


def test_a_web_client_ignores_a_refresh_placed_in_the_body(client, opened):
    """A valid refresh token arriving through an undeclared transport must be ignored."""
    response = client.post(URL, {"client": "web", "refresh": opened.pair.refresh}, format="json")

    assert response.status_code == 401
    assert response.data["error"]["code"] == "TOKEN_INVALID"


def test_a_mobile_client_ignores_the_cookie(client, opened, settings):
    """The symmetric case for the other transport."""
    client.cookies[settings.REFRESH_COOKIE_NAME] = opened.pair.refresh

    response = client.post(URL, {"client": "mobile"}, format="json")

    assert response.status_code == 401
    assert response.data["error"]["code"] == "TOKEN_INVALID"


def test_the_cookie_wins_for_a_web_client_when_both_are_present(client, service, opened, settings):
    """When both transports contain different tokens, only the declared source is consumed."""
    other = service.login(LoginCommand(email="supporter@example.test", password=PASSWORD))
    client.cookies[settings.REFRESH_COOKIE_NAME] = opened.pair.refresh

    response = client.post(URL, {"client": "web", "refresh": other.pair.refresh}, format="json")

    assert response.status_code == 200, response.data

    # The body token remains usable, proving the previous call did not consume it.
    second = client.post(URL, {"client": "mobile", "refresh": other.pair.refresh}, format="json")
    assert second.status_code == 200, second.data


# ===========================================================================
# Corps et erreurs
# ===========================================================================


def test_the_client_field_is_required(client, opened, settings):
    client.cookies[settings.REFRESH_COOKIE_NAME] = opened.pair.refresh

    response = client.post(URL, {}, format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


def test_a_missing_token_is_a_401_not_a_400(client, fan):
    """Missing-source failures remain opaque rather than revealing transport expectations."""
    response = client.post(URL, {"client": "web"}, format="json")

    assert response.status_code == 401
    assert response.data["error"]["code"] == "TOKEN_INVALID"


def test_replaying_a_rotated_token_returns_token_reuse_detected(client, opened):
    first = client.post(URL, {"client": "mobile", "refresh": opened.pair.refresh}, format="json")
    assert first.status_code == 200, first.data

    replay = client.post(URL, {"client": "mobile", "refresh": opened.pair.refresh}, format="json")

    assert replay.status_code == 401
    assert replay.data["error"]["code"] == "TOKEN_REUSE_DETECTED"


def test_a_wrong_fingerprint_returns_device_mismatch(client, opened_on_phone):
    response = client.post(
        URL,
        {"client": "mobile", "refresh": opened_on_phone.pair.refresh, "fingerprint": TABLET},
        format="json",
    )

    assert response.status_code == 401
    assert response.data["error"]["code"] == "DEVICE_MISMATCH"


def test_the_response_carries_the_user_so_a_role_change_is_visible(client, opened, fan, roles):
    """
    The refreshed access token carries the current role so the client does not need a separate role
    lookup.
    """
    User.objects.filter(pk=fan.pk).update(role=roles["ORGANIZER"])

    response = client.post(URL, {"client": "mobile", "refresh": opened.pair.refresh}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["user"]["role"] == "ORGANIZER"


def test_the_refresh_token_never_appears_twice(client, opened, settings):
    """Cookie and response body must never both carry the same refresh token."""
    client.cookies[settings.REFRESH_COOKIE_NAME] = opened.pair.refresh

    response = client.post(URL, {"client": "web"}, format="json")

    assert response.cookies[settings.REFRESH_COOKIE_NAME].value not in response.content.decode()


# ===========================================================================
# Limitation de debit
# ===========================================================================


def test_the_endpoint_is_throttled_per_session(client, monkeypatch):
    from apps.identity.throttling import RefreshSessionRateThrottle

    monkeypatch.setattr(
        RefreshSessionRateThrottle,
        "THROTTLE_RATES",
        {"refresh": "2/min"},
    )
    monkeypatch.setattr(
        RefreshSessionRateThrottle,
        "get_cache_key",
        lambda self, request, view: self.cache_format % {"scope": self.scope, "ident": "session-test"},
    )

    codes = [
        client.post(
            URL,
            {"client": "web"},
            format="json",
        ).status_code
        for _ in range(4)
    ]

    assert codes[:2] == [401, 401]
    assert codes[2] == 429, codes


@override_settings(
    REFRESH_REQUIRE_TRUSTED_ORIGIN=True,
    CSRF_TRUSTED_ORIGINS=["https://app.fanid.example"],
)
def test_web_refresh_rejects_untrusted_origin(
    client,
    opened,
    settings,
):
    client.cookies[settings.REFRESH_COOKIE_NAME] = opened.pair.refresh

    response = client.post(
        URL,
        {"client": "web"},
        format="json",
        HTTP_ORIGIN="https://attacker.example",
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "CSRF_ORIGIN_DENIED"


@override_settings(
    REFRESH_REQUIRE_TRUSTED_ORIGIN=True,
    CSRF_TRUSTED_ORIGINS=["https://app.fanid.example"],
)
def test_web_refresh_requires_origin_when_protection_is_enabled(
    client,
    opened,
    settings,
):
    client.cookies[settings.REFRESH_COOKIE_NAME] = opened.pair.refresh

    response = client.post(
        URL,
        {"client": "web"},
        format="json",
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "CSRF_ORIGIN_DENIED"


@override_settings(
    REFRESH_REQUIRE_TRUSTED_ORIGIN=True,
    CSRF_TRUSTED_ORIGINS=["https://app.fanid.example"],
)
def test_web_refresh_accepts_trusted_origin(
    client,
    opened,
    settings,
):
    client.cookies[settings.REFRESH_COOKIE_NAME] = opened.pair.refresh

    response = client.post(
        URL,
        {"client": "web"},
        format="json",
        HTTP_ORIGIN="https://app.fanid.example",
    )

    assert response.status_code == 200


def test_invalid_refresh_attempts_are_throttled_by_origin(
    client,
    monkeypatch,
):
    from apps.identity.throttling import RefreshOriginRateThrottle

    monkeypatch.setattr(
        RefreshOriginRateThrottle,
        "THROTTLE_RATES",
        {"refresh_origin": "2/min"},
    )

    codes = [
        client.post(
            URL,
            {
                "client": "mobile",
                "refresh": "invalid-refresh-token",
            },
            format="json",
        ).status_code
        for _ in range(4)
    ]

    assert codes[:2] == [401, 401]
    assert codes[2] == 429, codes
