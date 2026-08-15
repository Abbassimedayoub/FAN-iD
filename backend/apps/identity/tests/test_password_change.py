"""
`POST /api/v1/auth/password/change` — deconnexion totale, sans exception.

Le test qui porte le lot est
`test_the_caller_own_session_is_revoked_too`. Epargner la session qui declenche
l operation serait la commodite evidente, et exactement l exception dont un
attaquant profiterait : c est peut-etre lui qui la declenche.
"""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.identity import authentication as auth_module
from apps.identity import views
from apps.identity.constants import PLATFORM_ANDROID, SESSION_REVOKED_PASSWORD_CHANGE
from apps.identity.models import Device, Session, User
from apps.identity.services.authentication import AuthenticationService, LoginCommand
from apps.identity.services.devices import DeviceBindingService

URL = "/api/v1/auth/password/change"
PASSWORD = "Chataigne-Orageuse-2026"
NEW_PASSWORD = "Grenadine-Tumultueuse-2027"
PHONE = "a" * 64


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttle-password-tests",
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
def in_memory_lock(binding, service, monkeypatch):
    monkeypatch.setattr(views, "build_authentication_service", lambda: service)
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
        date_of_birth=datetime.date(1996, 5, 4),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


def login(service, **overrides):
    values: dict = {"email": "supporter@example.test", "password": PASSWORD}
    values.update(overrides)
    return service.login(LoginCommand(**values))


def as_user(client: APIClient, pair) -> APIClient:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair.access}")
    return client


def body(**overrides) -> dict:
    payload = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    payload.update(overrides)
    return payload


# ===========================================================================
# L invariant du lot : personne n est epargne
# ===========================================================================


def test_the_caller_own_session_is_revoked_too(client, service, fan):
    """
    **Le test qui porte le lot.**

    Epargner la session appelante est la commodite evidente — l utilisateur
    reste connecte la ou il travaille. C est aussi l exception dont profiterait
    un attaquant qui vient de prendre la main : il changerait le mot de passe,
    ejecterait le proprietaire, et garderait sa propre session.
    """
    opened = login(service)

    response = as_user(client, opened.pair).post(URL, body(), format="json")

    assert response.status_code == 204, response.data
    assert Session.objects.get(pk=opened.pair.session.pk).revoked_at is not None


def test_every_session_of_the_account_falls(client, service, fan):
    first = login(service)
    second = login(service)
    third = login(service)

    as_user(client, first.pair).post(URL, body(), format="json")

    revoked = Session.objects.filter(user=fan, revoked_at__isnull=False).count()
    assert revoked == 3
    for pair in (first.pair, second.pair, third.pair):
        assert Session.objects.get(pk=pair.session.pk).revoked_reason == SESSION_REVOKED_PASSWORD_CHANGE


def test_the_access_token_stops_working_immediately(client, service, fan):
    opened = login(service)
    authenticated = as_user(client, opened.pair)
    assert authenticated.post(URL, body(), format="json").status_code == 204

    assert authenticated.post(URL, body(), format="json").status_code == 401


def test_the_sessions_of_another_account_are_untouched(client, service, fan, roles):
    other = User.objects.create_user(
        email="autre@example.test",
        password=PASSWORD,
        first_name="Sami",
        last_name="Karim",
        date_of_birth=datetime.date(1994, 2, 9),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )
    theirs = service.login(LoginCommand(email=other.email, password=PASSWORD))
    mine = login(service)

    as_user(client, mine.pair).post(URL, body(), format="json")

    assert Session.objects.get(pk=theirs.pair.session.pk).revoked_at is None


# ===========================================================================
# Le mot de passe lui-meme
# ===========================================================================


def test_the_new_password_replaces_the_old_one(client, service, fan):
    opened = login(service)

    as_user(client, opened.pair).post(URL, body(), format="json")

    fan.refresh_from_db()
    assert fan.check_password(NEW_PASSWORD)
    assert not fan.check_password(PASSWORD)


def test_the_account_can_log_in_again_with_the_new_password(client, service, fan):
    opened = login(service)
    as_user(client, opened.pair).post(URL, body(), format="json")

    reopened = service.login(LoginCommand(email="supporter@example.test", password=NEW_PASSWORD))

    assert reopened.user.pk == fan.pk


def test_neither_password_ever_appears_in_the_response(client, service, fan):
    opened = login(service)

    response = as_user(client, opened.pair).post(URL, body(), format="json")

    rendered = response.content.decode()
    assert PASSWORD not in rendered
    assert NEW_PASSWORD not in rendered


# ===========================================================================
# Refus
# ===========================================================================


def test_a_wrong_current_password_is_a_400_and_not_a_401(client, service, fan):
    """
    401 declencherait les intercepteurs des clients — rafraichissement puis
    deconnexion — pour une faute de frappe. Le jeton est valide ; c est un champ
    du corps qui ne l est pas.
    """
    opened = login(service)

    response = as_user(client, opened.pair).post(URL, body(current_password="Faux-2026"), format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert "current_password" in response.data["error"]["details"]


def test_a_wrong_current_password_changes_nothing_at_all(client, service, fan):
    """Un refus ne doit ni changer le mot de passe, ni fermer la moindre session."""
    opened = login(service)

    as_user(client, opened.pair).post(URL, body(current_password="Faux-2026"), format="json")

    fan.refresh_from_db()
    assert fan.check_password(PASSWORD)
    assert Session.objects.get(pk=opened.pair.session.pk).revoked_at is None


def test_reusing_the_same_password_is_refused(client, service, fan):
    """
    Un changement qui ne change rien revoquerait quand meme toutes les
    sessions : l utilisateur serait deconnecte partout pour rien.
    """
    opened = login(service)

    response = as_user(client, opened.pair).post(URL, body(new_password=PASSWORD), format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert "new_password" in response.data["error"]["details"]
    assert Session.objects.get(pk=opened.pair.session.pk).revoked_at is None


def test_a_weak_new_password_is_refused_without_being_echoed(client, service, fan):
    weak = "12345678901"
    opened = login(service)

    response = as_user(client, opened.pair).post(URL, body(new_password=weak), format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"
    assert weak not in response.content.decode()


def test_a_new_password_too_close_to_the_account_is_refused(client, service, fan):
    """
    `UserAttributeSimilarityValidator` recoit l utilisateur REEL, pas un
    candidat reconstruit : il peut donc comparer a l adresse et au nom du
    compte. Sans ce passage en contexte, il n aurait rien a comparer.
    """
    opened = login(service)

    response = as_user(client, opened.pair).post(URL, body(new_password="supporter@example.test"))

    assert response.status_code == 400


def test_an_anonymous_call_is_refused(client, fan):
    assert client.post(URL, body(), format="json").status_code == 401


def test_the_device_is_not_revoked(client, service, fan):
    """
    Liberer le verrou d appareil ouvrirait la place au moment precis ou le
    compte est presume compromis : le premier a se connecter lierait le sien,
    sans garantie que ce soit le proprietaire.
    """
    opened = login(service, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    as_user(client, opened.pair).post(URL, body(), format="json")

    assert Device.objects.get(pk=opened.device.pk).revoked_at is None


def test_the_endpoint_is_throttled_per_account(client, service, fan, monkeypatch):
    """
    On echoue volontairement sur le mot de passe actuel : un succes revoquerait
    la session et la requete suivante serait refusee par l authentification
    avant meme d atteindre le compteur.
    """
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"password_change": "2/min"})
    opened = login(service)
    authenticated = as_user(client, opened.pair)

    codes = [
        authenticated.post(URL, body(current_password="Faux-2026"), format="json").status_code
        for _ in range(4)
    ]

    assert codes[:2] == [400, 400]
    assert codes[2] == 429, codes
