"""
GET /api/v1/devices/me — appareil actif + historique révoqué.

Le contrat important est fermé :
- aucun appareil d'un autre utilisateur ;
- jamais de fingerprint ;
- historique limité à 20 ;
- ordre du plus récent au plus ancien.
"""

from __future__ import annotations

import datetime

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.identity import authentication as auth_module
from apps.identity.constants import PLATFORM_ANDROID
from apps.identity.models import Device, User
from apps.identity.services.authentication import AuthenticationService, LoginCommand
from apps.identity.services.devices import DeviceBindingService

URL = "/api/v1/devices/me"
PASSWORD = "Chataigne-Orageuse-2026"
FINGERPRINT = "a" * 64


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttle-devices-me-tests",
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
    monkeypatch.setattr(auth_module, "default_binding_service", lambda: binding)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def make_user(roles, email: str) -> User:
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
def fan(db, roles) -> User:
    return make_user(roles, "supporter@example.test")


@pytest.fixture
def other_user(db, roles) -> User:
    return make_user(roles, "other@example.test")


def login(
    service: AuthenticationService,
    *,
    email: str = "supporter@example.test",
    fingerprint: str | None = None,
):
    kwargs = {
        "email": email,
        "password": PASSWORD,
    }
    if fingerprint is not None:
        kwargs.update(
            {
                "fingerprint": fingerprint,
                "platform": PLATFORM_ANDROID,
                "label": "Telephone",
            }
        )
    return service.login(LoginCommand(**kwargs))


def as_user(client: APIClient, pair) -> APIClient:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair.access}")
    return client


def test_no_device_returns_null_active_and_empty_history(client, service, fan):
    opened = login(service)

    response = as_user(client, opened.pair).get(URL)

    assert response.status_code == 200, response.data
    assert set(response.data) == {"active", "history"}
    assert response.data["active"] is None
    assert response.data["history"] == []


def test_active_device_has_exact_public_shape_without_fingerprint(
    client,
    service,
    fan,
):
    opened = login(service, fingerprint=FINGERPRINT)

    response = as_user(client, opened.pair).get(URL)

    assert response.status_code == 200, response.data
    assert response.data["active"] is not None

    active = response.data["active"]

    assert set(active) == {
        "id",
        "label",
        "platform",
        "bound_at",
        "last_seen_at",
        "revoked_at",
        "revoked_reason",
    }
    assert active["id"] == str(opened.device.pk)
    assert active["label"] == "Telephone"
    assert active["platform"] == PLATFORM_ANDROID
    assert active["revoked_at"] is None
    assert active["revoked_reason"] is None
    assert "fingerprint" not in active


def test_revoked_devices_are_returned_newest_first(
    client,
    service,
    fan,
):
    opened = login(service)

    old = Device.objects.create(
        user=fan,
        fingerprint="b" * 64,
        label="Ancien",
        platform=PLATFORM_ANDROID,
        revoked_at=timezone.now() - datetime.timedelta(days=10),
        revoked_reason="USER_RESET",
    )
    recent = Device.objects.create(
        user=fan,
        fingerprint="c" * 64,
        label="Recent",
        platform=PLATFORM_ANDROID,
        revoked_at=timezone.now() - datetime.timedelta(days=2),
        revoked_reason="USER_RESET",
    )

    # bound_at est auto_now_add : on fixe explicitement l'ordre après création.
    Device.objects.filter(pk=old.pk).update(bound_at=timezone.now() - datetime.timedelta(days=20))
    Device.objects.filter(pk=recent.pk).update(bound_at=timezone.now() - datetime.timedelta(days=3))

    response = as_user(client, opened.pair).get(URL)

    assert response.status_code == 200, response.data
    assert response.data["active"] is None
    assert [item["id"] for item in response.data["history"]] == [
        str(recent.pk),
        str(old.pk),
    ]

    for item in response.data["history"]:
        assert set(item) == {
            "id",
            "label",
            "platform",
            "bound_at",
            "last_seen_at",
            "revoked_at",
            "revoked_reason",
        }
        assert "fingerprint" not in item


def test_devices_from_other_users_never_appear(
    client,
    service,
    fan,
    other_user,
):
    mine = login(service)
    foreign = Device.objects.create(
        user=other_user,
        fingerprint="d" * 64,
        label="Etranger",
        platform=PLATFORM_ANDROID,
    )

    response = as_user(client, mine.pair).get(URL)

    assert response.status_code == 200, response.data

    ids = set()
    if response.data["active"] is not None:
        ids.add(response.data["active"]["id"])
    ids.update(item["id"] for item in response.data["history"])

    assert str(foreign.pk) not in ids


def test_history_is_capped_at_twenty(client, service, fan):
    opened = login(service)

    for index in range(25):
        device = Device.objects.create(
            user=fan,
            fingerprint=f"{index:064x}",
            label=f"Device-{index}",
            platform=PLATFORM_ANDROID,
            revoked_at=timezone.now(),
            revoked_reason="USER_RESET",
        )
        Device.objects.filter(pk=device.pk).update(
            bound_at=timezone.now() - datetime.timedelta(minutes=index)
        )

    response = as_user(client, opened.pair).get(URL)

    assert response.status_code == 200, response.data
    assert len(response.data["history"]) == 20


def test_anonymous_call_is_refused(client, fan):
    assert client.get(URL).status_code == 401
