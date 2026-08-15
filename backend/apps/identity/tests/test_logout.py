"""
`POST /api/v1/auth/logout` — revocation immediate et portee.

Deux tests portent le lot : celui qui prouve que le jeton d acces cesse de
fonctionner AUSSITOT — ce qui n aurait rien d automatique si la classe
d authentification se contentait des claims — et celui qui prouve que les
AUTRES sessions du compte survivent.
"""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.identity import authentication as auth_module
from apps.identity import views
from apps.identity.constants import PLATFORM_ANDROID, SESSION_REVOKED_LOGOUT
from apps.identity.models import Device, Session, User
from apps.identity.services.authentication import AuthenticationService, LoginCommand
from apps.identity.services.devices import DeviceBindingService

URL = "/api/v1/auth/logout"
PASSWORD = "Chataigne-Orageuse-2026"
PHONE = "a" * 64


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    """Compteur local au test — voir `test_login_endpoint.py`."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttle-logout-tests",
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
    """
    Deux points a remplacer, pas un.

    La VUE construit son service via `build_authentication_service()`, mais la
    classe d AUTHENTIFICATION resout le sien par `default_binding_service()` —
    qui ouvre une vraie connexion Redis. Sans ce second remplacement, les tests
    de bout en bout dependraient du cache partage entre processus.
    """
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


# ===========================================================================
# Revocation
# ===========================================================================


def test_a_logout_revokes_the_current_session(client, service, fan):
    opened = login(service)

    response = as_user(client, opened.pair).post(URL)

    assert response.status_code == 204, response.data
    session = Session.objects.get(pk=opened.pair.session.pk)
    assert session.revoked_at is not None
    assert session.revoked_reason == SESSION_REVOKED_LOGOUT


def test_the_access_token_stops_working_immediately(client, service, fan):
    """
    **Le test qui porte le lot.**

    Une integration JWT qui fabrique l utilisateur a partir des seuls claims
    laisserait ce jeton valable jusqu a son expiration — quinze minutes pendant
    lesquelles une deconnexion demandee n aurait produit aucun effet. C est la
    relecture de session a chaque requete (S1-A.6a) qui rend la revocation
    immediate, et ce test est ce qui l empeche de disparaitre.
    """
    opened = login(service)
    authenticated = as_user(client, opened.pair)
    assert authenticated.post(URL).status_code == 204

    replay = authenticated.post(URL)

    assert replay.status_code == 401


def test_the_refresh_token_dies_with_the_session(client, service, fan):
    """Revoquer la session sans tuer le refresh laisserait rouvrir l acces."""
    from apps.identity.services.authentication import RefreshCommand
    from apps.identity.tokens import TokenInvalidError

    opened = login(service)
    as_user(client, opened.pair).post(URL)

    with pytest.raises(TokenInvalidError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh))


def test_a_second_logout_returns_401_without_any_double_effect(client, service, fan):
    """
    Idempotence structurelle (ADR-S1-03). Le rejeu ne peut rien casser : la
    session est deja revoquee, la date de revocation ne bouge pas.
    """
    opened = login(service)
    authenticated = as_user(client, opened.pair)
    authenticated.post(URL)
    first_revocation = Session.objects.get(pk=opened.pair.session.pk).revoked_at

    assert authenticated.post(URL).status_code == 401
    assert Session.objects.get(pk=opened.pair.session.pk).revoked_at == first_revocation


# ===========================================================================
# Portee
# ===========================================================================


def test_the_other_sessions_of_the_account_survive(client, service, fan):
    """
    Se deconnecter d un appareil ne ferme pas les autres. `revoke_family` est
    reserve a la detection de reutilisation, ou l on ignore lequel des porteurs
    est l attaquant — ici on le sait, c est celui qui demande.
    """
    first = login(service)
    second = login(service)

    as_user(client, first.pair).post(URL)

    assert Session.objects.get(pk=first.pair.session.pk).revoked_at is not None
    assert Session.objects.get(pk=second.pair.session.pk).revoked_at is None


def test_a_logout_does_not_revoke_the_device(client, service, fan):
    """
    Se deconnecter n est pas perdre son telephone. Liberer le verrou ici
    obligerait a repasser par la liaison a chaque reconnexion, et ouvrirait la
    place a un autre appareil entre les deux.
    """
    opened = login(service, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    as_user(client, opened.pair).post(URL)

    assert Device.objects.get(pk=opened.device.pk).revoked_at is None


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

    as_user(client, mine.pair).post(URL)

    assert Session.objects.get(pk=theirs.pair.session.pk).revoked_at is None


# ===========================================================================
# Transport et refus
# ===========================================================================


def test_the_refresh_cookie_is_cleared(client, service, fan, settings):
    """
    Le jeton est mort en base, mais laisser le cookie ferait envoyer a chaque
    appel un jeton que le serveur rejettera — et donnerait au navigateur
    l illusion d une session vivante.
    """
    opened = login(service)
    client.cookies[settings.REFRESH_COOKIE_NAME] = opened.pair.refresh

    response = as_user(client, opened.pair).post(URL)

    cookie = response.cookies[settings.REFRESH_COOKIE_NAME]
    assert cookie.value == ""
    assert cookie["path"] == settings.REFRESH_COOKIE_PATH


def test_an_anonymous_call_is_refused(client, fan):
    assert client.post(URL).status_code == 401


def test_the_endpoint_is_throttled_per_account(client, service, fan, monkeypatch):
    """
    Trois sessions distinctes, un seul compte : le compteur doit les additionner.
    Sans quoi le quota se contournerait en ouvrant une session de plus.
    """
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"logout": "2/min"})
    pairs = [login(service).pair for _ in range(3)]

    codes = [as_user(APIClient(), pair).post(URL).status_code for pair in pairs]

    assert codes[:2] == [204, 204]
    assert codes[2] == 429, codes
