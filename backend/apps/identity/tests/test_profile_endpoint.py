"""
GET/PATCH /api/v1/auth/me — profil self-service versionné.

Ce module prouve notamment :
- le contrat ETag / If-Match ;
- l'absence de sur-postage ;
- la séparation des quotas GET et PATCH ;
- la mise à jour optimiste via la version réelle du User.
"""

from __future__ import annotations

import datetime

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.identity import authentication as auth_module
from apps.identity.models import User
from apps.identity.services.authentication import AuthenticationService, LoginCommand
from apps.identity.services.devices import DeviceBindingService

URL = "/api/v1/auth/me"
PASSWORD = "Chataigne-Orageuse-2026"
PHONE = "a" * 64


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttle-profile-tests",
        }
    }
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
def in_memory_lock(binding, monkeypatch):
    # JWTAuthentication construit son propre binding service.
    monkeypatch.setattr(auth_module, "default_binding_service", lambda: binding)


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
        phone="+33601020304",
        date_of_birth=datetime.date(1996, 5, 4),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


def login(service: AuthenticationService, **overrides):
    values: dict = {
        "email": "supporter@example.test",
        "password": PASSWORD,
    }
    values.update(overrides)
    return service.login(LoginCommand(**values))


def as_user(client: APIClient, pair) -> APIClient:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair.access}")
    return client


def test_get_returns_private_profile_and_strong_etag(client, service, fan):
    opened = login(service)
    response = as_user(client, opened.pair).get(URL)

    assert response.status_code == 200, response.data

    assert set(response.data) == {
        "id",
        "email",
        "first_name",
        "last_name",
        "phone",
        "date_of_birth",
        "role",
        "created_at",
        "updated_at",
        "version",
    }

    assert response.data["id"] == str(fan.pk)
    assert response.data["email"] == fan.email
    assert response.data["first_name"] == "Ines"
    assert response.data["last_name"] == "Bouzid"
    assert response.data["phone"] == "+33601020304"
    assert response.data["version"] == fan.version
    assert response["ETag"] == f'"{fan.version}"'


def test_patch_updates_only_allowed_fields_and_increments_version_once(client, service, fan):
    opened = login(service)

    fan.refresh_from_db()
    initial_version = fan.version
    initial_updated_at = fan.updated_at

    response = as_user(client, opened.pair).patch(
        URL,
        {
            "first_name": "Ines-2",
            "last_name": "Bouzid-2",
            "phone": "+33699999999",
        },
        format="json",
        HTTP_IF_MATCH=f'"{initial_version}"',
    )

    assert response.status_code == 200, response.data

    fan.refresh_from_db()

    assert fan.first_name == "Ines-2"
    assert fan.last_name == "Bouzid-2"
    assert fan.phone == "+33699999999"
    assert fan.version == initial_version + 1
    assert fan.updated_at > initial_updated_at

    assert response.data["version"] == initial_version + 1
    assert response["ETag"] == f'"{initial_version + 1}"'


def test_patch_without_if_match_returns_428(client, service, fan):
    opened = login(service)

    response = as_user(client, opened.pair).patch(
        URL,
        {"first_name": "Nouvelle"},
        format="json",
    )

    assert response.status_code == 428, response.data
    assert response.data["error"]["code"] == "PRECONDITION_REQUIRED"


def test_patch_with_stale_version_returns_current_version(client, service, fan):
    opened = login(service)

    fan.refresh_from_db()
    stale_version = fan.version

    first = as_user(client, opened.pair).patch(
        URL,
        {"first_name": "Version-2"},
        format="json",
        HTTP_IF_MATCH=f'"{stale_version}"',
    )
    assert first.status_code == 200, first.data

    second = client.patch(
        URL,
        {"last_name": "Perdant"},
        format="json",
        HTTP_IF_MATCH=f'"{stale_version}"',
    )

    assert second.status_code == 409, second.data
    assert second.data["error"]["code"] == "STALE_RESOURCE"
    assert second.data["error"]["details"]["current_version"] == stale_version + 1


def test_overposting_is_ignored_and_forbidden_fields_remain_unchanged(client, service, fan, roles):
    opened = login(service)

    fan.refresh_from_db()
    initial_version = fan.version
    initial_email = fan.email
    initial_birth = fan.date_of_birth
    initial_role_id = fan.role_id
    initial_active = fan.is_active

    response = as_user(client, opened.pair).patch(
        URL,
        {
            "first_name": "Autorise",
            "email": "attacker@example.test",
            "date_of_birth": "2015-01-01",
            "role": "ADMIN",
            "role_id": str(roles["ADMIN"].pk),
            "is_active": False,
            "version": 9999,
            "is_staff": True,
            "is_superuser": True,
        },
        format="json",
        HTTP_IF_MATCH=f'"{initial_version}"',
    )

    assert response.status_code == 200, response.data

    fan.refresh_from_db()

    assert fan.first_name == "Autorise"
    assert fan.email == initial_email
    assert fan.date_of_birth == initial_birth
    assert fan.role_id == initial_role_id
    assert fan.is_active == initial_active
    assert fan.is_staff is False
    assert fan.is_superuser is False
    assert fan.version == initial_version + 1


def test_patch_with_only_unknown_fields_is_a_noop(client, service, fan):
    opened = login(service)

    fan.refresh_from_db()
    initial_version = fan.version
    initial_updated_at = fan.updated_at

    response = as_user(client, opened.pair).patch(
        URL,
        {
            "email": "attacker@example.test",
            "version": 999,
        },
        format="json",
        HTTP_IF_MATCH=f'"{initial_version}"',
    )

    assert response.status_code == 200, response.data

    fan.refresh_from_db()

    assert fan.email == "supporter@example.test"
    assert fan.version == initial_version
    assert fan.updated_at == initial_updated_at
    assert response["ETag"] == f'"{initial_version}"'


def test_empty_patch_is_a_noop(client, service, fan):
    opened = login(service)

    fan.refresh_from_db()
    initial_version = fan.version

    response = as_user(client, opened.pair).patch(
        URL,
        {},
        format="json",
        HTTP_IF_MATCH=f'"{initial_version}"',
    )

    assert response.status_code == 200, response.data

    fan.refresh_from_db()
    assert fan.version == initial_version
    assert response["ETag"] == f'"{initial_version}"'


def test_empty_patch_with_stale_version_is_still_rejected(client, service, fan):
    opened = login(service)

    fan.refresh_from_db()
    stale_version = fan.version

    changed = as_user(client, opened.pair).patch(
        URL,
        {"first_name": "Version-2"},
        format="json",
        HTTP_IF_MATCH=f'"{stale_version}"',
    )
    assert changed.status_code == 200, changed.data

    response = client.patch(
        URL,
        {},
        format="json",
        HTTP_IF_MATCH=f'"{stale_version}"',
    )

    assert response.status_code == 409, response.data
    assert response.data["error"]["details"]["current_version"] == stale_version + 1


def test_anonymous_get_and_patch_are_refused(client, fan):
    assert client.get(URL).status_code == 401

    response = client.patch(
        URL,
        {"first_name": "Interdit"},
        format="json",
        HTTP_IF_MATCH=f'"{fan.version}"',
    )
    assert response.status_code == 401


def test_patch_has_its_own_scope_but_get_keeps_user_rate(client, service, fan, monkeypatch):
    """
    Deux PATCH consomment profile_update ; le troisième prend 429.

    Le GET qui suit doit néanmoins rester autorisé, ce qui prouve que MeView
    n'applique pas accidentellement la portée 20/h aux lectures.
    """
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {"profile_update": "2/min"},
    )

    opened = login(service)
    authenticated = as_user(client, opened.pair)

    fan.refresh_from_db()
    etag = f'"{fan.version}"'

    codes = [
        authenticated.patch(
            URL,
            {},
            format="json",
            HTTP_IF_MATCH=etag,
        ).status_code
        for _ in range(3)
    ]

    assert codes == [200, 200, 429], codes

    get_response = authenticated.get(URL)
    assert get_response.status_code == 200, get_response.data
