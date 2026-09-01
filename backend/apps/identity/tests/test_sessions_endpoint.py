"""
Surface self-service des sessions.

Les tests importants ne se contentent pas d'inspecter la base :
- la portée multi-tenant est prouvée par HTTP ;
- les clés de sortie sont figées exactement ;
- révoquer la session courante est suivi d'une DEUXIÈME requête avec le même
  access token, qui doit être refusée par Zero Trust.
"""

from __future__ import annotations

import datetime

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.identity import authentication as auth_module
from apps.identity.constants import SESSION_REVOKED_LOGOUT
from apps.identity.models import Session, User
from apps.identity.services.authentication import AuthenticationService, LoginCommand
from apps.identity.services.devices import DeviceBindingService
from apps.identity.services.tokens import TokenService

LIST_URL = "/api/v1/auth/sessions"
ME_URL = "/api/v1/auth/me"
PASSWORD = "Chataigne-Orageuse-2026"


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttle-sessions-tests",
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


def login(service: AuthenticationService, email: str = "supporter@example.test"):
    return service.login(
        LoginCommand(
            email=email,
            password=PASSWORD,
        )
    )


def as_user(client: APIClient, pair) -> APIClient:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair.access}")
    return client


def session_url(session: Session) -> str:
    return f"/api/v1/auth/sessions/{session.pk}"


def test_list_contains_real_sessions_with_exact_public_shape(client, service, fan):
    current = login(service)
    another = login(service)

    response = as_user(client, current.pair).get(LIST_URL)

    assert response.status_code == 200, response.data
    assert len(response.data) == 2

    expected_keys = {
        "id",
        "device",
        "ip",
        "user_agent",
        "issued_at",
        "last_used_at",
        "expires_at",
        "current",
    }

    for item in response.data:
        assert set(item) == expected_keys

    ids = {item["id"] for item in response.data}
    assert ids == {
        str(current.pair.session.pk),
        str(another.pair.session.pk),
    }

    current_rows = [item for item in response.data if item["current"]]
    assert len(current_rows) == 1
    assert current_rows[0]["id"] == str(current.pair.session.pk)


def test_list_never_exposes_internal_token_identifiers(client, service, fan):
    opened = login(service)

    response = as_user(client, opened.pair).get(LIST_URL)

    assert response.status_code == 200, response.data
    assert len(response.data) == 1

    item = response.data[0]
    assert set(item) == {
        "id",
        "device",
        "ip",
        "user_agent",
        "issued_at",
        "last_used_at",
        "expires_at",
        "current",
    }

    # Les assertions explicites documentent le motif de sécurité.
    assert "refresh_jti" not in item
    assert "family_id" not in item


def test_list_excludes_sessions_from_other_users(client, service, fan, other_user):
    mine = login(service)
    foreign = login(service, email=other_user.email)

    response = as_user(client, mine.pair).get(LIST_URL)

    assert response.status_code == 200, response.data

    ids = {item["id"] for item in response.data}
    assert str(mine.pair.session.pk) in ids
    assert str(foreign.pair.session.pk) not in ids


def test_list_excludes_revoked_and_expired_sessions(client, service, fan):
    current = login(service)
    revoked = login(service)
    expired = login(service)

    TokenService.revoke_session(
        revoked.pair.session,
        SESSION_REVOKED_LOGOUT,
    )

    now = timezone.now()
    Session.objects.filter(pk=expired.pair.session.pk).update(
        issued_at=now - datetime.timedelta(hours=2),
        last_used_at=now - datetime.timedelta(hours=2),
        expires_at=now - datetime.timedelta(hours=1),
    )

    response = as_user(client, current.pair).get(LIST_URL)

    assert response.status_code == 200, response.data

    ids = {item["id"] for item in response.data}
    assert str(current.pair.session.pk) in ids
    assert str(revoked.pair.session.pk) not in ids
    assert str(expired.pair.session.pk) not in ids


def test_revoke_another_own_session_returns_204_and_sets_reason(client, service, fan):
    current = login(service)
    target = login(service)

    response = as_user(client, current.pair).delete(session_url(target.pair.session))

    assert response.status_code == 204

    target.pair.session.refresh_from_db()
    assert target.pair.session.revoked_at is not None
    assert target.pair.session.revoked_reason == SESSION_REVOKED_LOGOUT

    # La session appelante reste valide.
    still_authenticated = client.get(ME_URL)
    assert still_authenticated.status_code == 200, still_authenticated.data


def test_revoke_current_session_invalidates_same_access_token_immediately(
    client,
    service,
    fan,
):
    opened = login(service)
    authenticated = as_user(client, opened.pair)

    first = authenticated.delete(session_url(opened.pair.session))
    assert first.status_code == 204

    # Preuve Zero Trust : même access token, seconde requête HTTP.
    replay = authenticated.get(ME_URL)
    assert replay.status_code == 401, replay.data


def test_revoke_foreign_session_returns_404_not_403(
    client,
    service,
    fan,
    other_user,
):
    mine = login(service)
    foreign = login(service, email=other_user.email)

    response = as_user(client, mine.pair).delete(session_url(foreign.pair.session))

    assert response.status_code == 404, response.data

    foreign.pair.session.refresh_from_db()
    assert foreign.pair.session.revoked_at is None


def test_revoke_is_structurally_idempotent(client, service, fan):
    current = login(service)
    target = login(service)
    authenticated = as_user(client, current.pair)

    first = authenticated.delete(session_url(target.pair.session))
    second = authenticated.delete(session_url(target.pair.session))

    assert first.status_code == 204
    assert second.status_code == 204

    target.pair.session.refresh_from_db()
    assert target.pair.session.revoked_at is not None
    assert target.pair.session.revoked_reason == SESSION_REVOKED_LOGOUT


def test_list_scope_really_throttles(client, service, fan, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {"sessions_list": "2/min"},
    )

    opened = login(service)
    authenticated = as_user(client, opened.pair)

    codes = [authenticated.get(LIST_URL).status_code for _ in range(3)]

    assert codes == [200, 200, 429], codes


def test_revoke_scope_really_throttles(client, service, fan, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {"session_revoke": "2/min"},
    )

    current = login(service)
    targets = [login(service) for _ in range(3)]
    authenticated = as_user(client, current.pair)

    codes = [authenticated.delete(session_url(target.pair.session)).status_code for target in targets]

    assert codes == [204, 204, 429], codes


def test_anonymous_list_and_delete_are_refused(client, service, fan):
    target = login(service)

    assert client.get(LIST_URL).status_code == 401
    assert client.delete(session_url(target.pair.session)).status_code == 401
