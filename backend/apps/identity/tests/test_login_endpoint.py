"""
`POST /api/v1/auth/login` — transport du refresh et limitation de debit.

Le service est teste ailleurs (`test_login.py`). Ce fichier ne verifie que ce
qui appartient a la couche HTTP : le choix du transport, les en-tetes du cookie,
et les deux axes de limitation.
"""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.identity import views
from apps.identity.constants import (
    CLIENT_MOBILE,
    CLIENT_WEB,
    PLATFORM_ANDROID,
    PLATFORM_IOS,
    SESSION_REVOKED_REPLACED,
)
from apps.identity.models import Session, User
from apps.identity.services.authentication import AuthenticationService
from apps.identity.services.devices import DeviceBindingService

URL = "/api/v1/auth/login"
PASSWORD = "Chataigne-Orageuse-2026"
PHONE = "a" * 64
TABLET = "b" * 64


@pytest.fixture(autouse=True)
def isolated_throttle_cache(settings):
    """
    Compteur local au test.

    Sans cela, le compteur vit dans le Redis partage : les huit processus de
    `pytest -n auto` s incrementeraient mutuellement — toutes les requetes de
    test viennent de la meme adresse — et le premier test malchanceux recevrait
    un 429.
    """
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "throttle-login-tests",
        }
    }
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def binding() -> DeviceBindingService:
    return DeviceBindingService(lock=FakeDeviceLock())


@pytest.fixture(autouse=True)
def in_memory_lock(binding, monkeypatch):
    """
    La vue construit son service via `build_authentication_service()`. On
    remplace ce seul point : les tests n ouvrent donc aucune connexion Redis,
    et le verrou est remis a zero entre chaque cas.
    """
    monkeypatch.setattr(views, "build_authentication_service", lambda: AuthenticationService(binding=binding))


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


def payload(**overrides) -> dict:
    body = {"email": "supporter@example.test", "password": PASSWORD, "client": "web"}
    body.update(overrides)
    return body


# ===========================================================================
# Transport du jeton de rafraichissement
# ===========================================================================


def test_a_web_client_receives_the_refresh_only_in_an_httponly_cookie(client, fan, settings):
    """
    Le refresh ne doit PAS apparaitre dans le corps.

    S il y figurait, une injection JavaScript lisant la reponse de connexion
    obtiendrait le jeton — cookie HttpOnly ou pas. Les deux transports ne se
    cumulent pas : ils s annulent.
    """
    response = client.post(URL, payload(client="web"), format="json")

    assert response.status_code == 200, response.data
    assert "refresh" not in response.data
    assert "access" in response.data

    cookie = response.cookies[settings.REFRESH_COOKIE_NAME]
    assert cookie["httponly"] is True
    assert cookie["path"] == settings.REFRESH_COOKIE_PATH
    assert cookie["samesite"] == settings.REFRESH_COOKIE_SAMESITE
    assert cookie["expires"] == ""
    assert cookie["max-age"] == ""
    assert cookie.value not in response.content.decode()


def test_a_mobile_client_receives_the_refresh_in_the_body_and_no_cookie(client, fan, settings):
    """
    Le mobile depose le jeton dans le stockage securise du systeme
    (Keychain/Keystore), mieux protege qu un fichier de cookies applicatif.
    """
    response = client.post(URL, payload(client="mobile"), format="json")

    assert response.status_code == 200, response.data
    assert response.data["refresh"]
    assert settings.REFRESH_COOKIE_NAME not in response.cookies


def test_the_client_field_is_required(client, fan):
    """
    Deduire le client du `User-Agent` serait plus discret et beaucoup moins
    sur : cet en-tete se falsifie et change a chaque version de navigateur.
    """
    body = payload()
    del body["client"]

    response = client.post(URL, body, format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "VALIDATION_ERROR"


def test_an_unknown_client_value_is_refused(client, fan):
    assert client.post(URL, payload(client="smart-fridge"), format="json").status_code == 400


# ===========================================================================
# Corps de la reponse
# ===========================================================================


def test_the_password_never_appears_in_the_response(client, fan):
    response = client.post(URL, payload(), format="json")

    assert PASSWORD not in response.content.decode()


def test_the_response_carries_the_user_and_the_bound_device(client, fan):
    response = client.post(
        URL, payload(client="mobile", fingerprint=PHONE, platform=PLATFORM_ANDROID, label="Pixel 8")
    )

    assert response.status_code == 200, response.data
    assert response.data["user"]["email"] == "supporter@example.test"
    assert response.data["user"]["role"] == "FAN"
    assert response.data["device"]["label"] == "Pixel 8"


def test_a_login_without_fingerprint_reports_no_device(client, fan):
    response = client.post(URL, payload(), format="json")

    assert response.data["device"] is None


# ===========================================================================
# Erreurs
# ===========================================================================


def test_wrong_credentials_return_401_with_the_frozen_envelope(client, fan):
    response = client.post(URL, payload(password="Faux-Mot-De-Passe-2026"), format="json")

    assert response.status_code == 401
    assert response.data["error"]["code"] == "INVALID_CREDENTIALS"
    assert response.data["error"]["details"] == {}


def test_an_unknown_address_is_indistinguishable_from_a_wrong_password(client, fan):
    unknown = client.post(URL, payload(email="jamais-inscrit@example.test"), format="json")
    wrong = client.post(URL, payload(password="Faux-Mot-De-Passe-2026"), format="json")

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.data["error"]["code"] == wrong.data["error"]["code"]
    assert unknown.data["error"]["message"] == wrong.data["error"]["message"]


def test_a_second_device_gets_403_with_enough_detail_to_be_recognised(client, fan, binding):
    binding.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID, label="Pixel 8")

    response = client.post(
        URL, payload(client="mobile", fingerprint=TABLET, platform=PLATFORM_IOS), format="json"
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "DEVICE_LOCKED"
    assert response.data["error"]["details"]["reset_available"] is True


def test_a_wrong_password_on_a_locked_account_still_returns_401(client, fan, binding):
    """
    L invariant du lot, verifie cette fois DE BOUT EN BOUT : la couche HTTP ne
    doit pas reintroduire l ordre inverse que le service refuse.
    """
    binding.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    response = client.post(
        URL,
        payload(
            client="mobile", password="Faux-Mot-De-Passe-2026", fingerprint=TABLET, platform=PLATFORM_IOS
        ),
        format="json",
    )

    assert response.status_code == 401
    assert response.data["error"]["code"] == "INVALID_CREDENTIALS"


# ===========================================================================
# Limitation de debit — deux axes
# ===========================================================================


def test_the_same_address_is_throttled_even_from_different_ips(client, fan, monkeypatch):
    """
    **La moitie que DRF ne fournit pas.**

    Limiter par IP seule laisse passer une attaque distribuee : mille adresses
    testant chacune cinq mots de passe sur LE MEME compte restent sous le seuil.
    Ce test change d adresse a chaque tentative — seul le compteur par compte
    peut l arreter.
    """
    from apps.identity.throttling import LoginAccountRateThrottle

    monkeypatch.setattr(LoginAccountRateThrottle, "THROTTLE_RATES", {"login_account": "3/hour"})

    codes = [
        client.post(
            URL,
            payload(password="Faux-Mot-De-Passe-2026"),
            format="json",
            REMOTE_ADDR=f"203.0.113.{index}",
        ).status_code
        for index in range(1, 6)
    ]

    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429, codes


def test_a_single_address_is_throttled_by_origin_too(client, fan, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"login": "2/min"})

    codes = [
        client.post(URL, payload(password="Faux-Mot-De-Passe-2026"), format="json").status_code
        for _ in range(4)
    ]

    assert codes[:2] == [401, 401]
    assert codes[2] == 429, codes


def test_the_account_throttle_never_stores_the_address_in_clear(client, fan):
    """
    Les cles de Redis se listent, s exportent avec une sauvegarde et
    apparaissent dans les outils d exploitation. Y deposer l adresse de tous
    ceux qui tentent de se connecter transformerait le cache en annuaire.
    """
    from django.core.cache import cache

    from apps.identity.throttling import LoginAccountRateThrottle

    client.post(URL, payload(password="Faux-Mot-De-Passe-2026"), format="json")
    key = LoginAccountRateThrottle().get_cache_key(_FakeRequest(payload()), None)

    assert key is not None
    assert "supporter@example.test" not in key
    assert cache.get(key) is not None, "le compteur doit bien exister sous cette cle"


def test_the_account_throttle_ignores_the_case_of_the_address():
    """
    `Ines@Example.test` et `ines@example.test` designent le meme compte — la
    colonne est `citext`. Deux compteurs distincts offriraient le double du
    quota a qui varie la casse.
    """
    from apps.identity.throttling import LoginAccountRateThrottle

    throttle = LoginAccountRateThrottle()
    first = throttle.get_cache_key(_FakeRequest({"email": "Supporter@Example.TEST"}), None)
    second = throttle.get_cache_key(_FakeRequest({"email": " supporter@example.test "}), None)

    assert first == second


def test_a_request_without_any_address_is_not_throttled_by_account():
    """Rien a limiter : le serialiseur renverra un 400 juste apres."""
    from apps.identity.throttling import LoginAccountRateThrottle

    assert LoginAccountRateThrottle().get_cache_key(_FakeRequest({}), None) is None


class _FakeRequest:
    """Requete minimale : la classe de limitation ne lit que `data`."""

    def __init__(self, data: dict) -> None:
        self.data = data


def test_a_second_web_login_replaces_only_the_previous_web_session(client, fan):
    first = client.post(URL, payload(client="web"), format="json")
    assert first.status_code == 200, first.data

    first_access = first.data["access"]
    first_session = Session.objects.get(
        user=fan,
        client=CLIENT_WEB,
        revoked_at__isnull=True,
    )

    second = client.post(URL, payload(client="web"), format="json")
    assert second.status_code == 200, second.data

    first_session.refresh_from_db()
    assert first_session.revoked_at is not None
    assert first_session.revoked_reason == SESSION_REVOKED_REPLACED

    active_web = Session.objects.filter(
        user=fan,
        client=CLIENT_WEB,
        revoked_at__isnull=True,
    )
    assert active_web.count() == 1
    assert active_web.get().pk != first_session.pk

    old_browser = APIClient()
    old_browser.credentials(HTTP_AUTHORIZATION=f"Bearer {first_access}")
    assert old_browser.get("/api/v1/auth/me").status_code == 401


def test_a_new_web_login_never_revokes_the_mobile_session(client, fan):
    mobile = client.post(
        URL,
        payload(
            client="mobile",
            fingerprint=PHONE,
            platform=PLATFORM_ANDROID,
            label="Pixel 8",
        ),
        format="json",
    )
    assert mobile.status_code == 200, mobile.data

    mobile_session = Session.objects.get(
        user=fan,
        client=CLIENT_MOBILE,
        revoked_at__isnull=True,
    )

    web = client.post(URL, payload(client="web"), format="json")
    assert web.status_code == 200, web.data

    mobile_session.refresh_from_db()
    assert mobile_session.revoked_at is None
    assert mobile_session.revoked_reason is None

    assert (
        Session.objects.filter(
            user=fan,
            client=CLIENT_WEB,
            revoked_at__isnull=True,
        ).count()
        == 1
    )
