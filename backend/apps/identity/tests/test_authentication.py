"""
Classe d authentification : un jeton devient un utilisateur, ou rien.

Deux tests portent le fond du lot : celui qui prouve qu une session revoquee est
refusee IMMEDIATEMENT, et celui qui prouve que le claim `role` du jeton
n autorise rien. Les autres verifient les refus de forme.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.identity.authentication import JWTAuthentication
from apps.identity.authz import Action, Resource, authorize
from apps.identity.authz.context import subject_from_request
from apps.identity.constants import AUTH_LEVEL_STEP_UP, PLATFORM_ANDROID, SESSION_REVOKED_LOGOUT
from apps.identity.exceptions import DeviceMismatchError
from apps.identity.models import Session, User
from apps.identity.services.devices import DeviceBindingService
from apps.identity.services.tokens import TokenService
from apps.identity.tokens import TokenInvalidError

factory = APIRequestFactory()
PHONE = "a" * 64


@pytest.fixture
def binding() -> DeviceBindingService:
    return DeviceBindingService(lock=FakeDeviceLock())


@pytest.fixture
def auth(binding) -> JWTAuthentication:
    return JWTAuthentication(binding_service=binding)


def make_user(roles, role: str = "FAN", email: str | None = None) -> User:
    return User.objects.create_user(
        email=email or f"{role.lower()}-auth@example.test",
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1996, 5, 4),
        terms_accepted_at=timezone.now(),
        role=roles[role],
    )


@pytest.fixture
def fan(db, roles) -> User:
    return make_user(roles)


def request_with(token: str | None, *, scheme: str = "Bearer"):
    headers = {} if token is None else {"HTTP_AUTHORIZATION": f"{scheme} {token}".strip()}
    return factory.get("/api/v1/whatever", **headers)


# ===========================================================================
# Chemin nominal
# ===========================================================================


def test_a_valid_token_resolves_the_user(auth, fan):
    pair = TokenService.issue_pair(user=fan)

    resolved, claims = auth.authenticate(request_with(pair.access))

    assert resolved.pk == fan.pk
    assert claims["sid"] == str(pair.session.pk)


def test_the_authentication_level_is_read_from_the_session_not_from_the_token(auth, fan):
    """
    Une elevation en verification renforcee met a jour la SESSION. Le jeton emis
    avant porte encore l ancien niveau : lire le jeton ferait attendre quinze
    minutes a l utilisateur qui vient de saisir son code — et, plus grave,
    ignorerait une RETROGRADATION.
    """
    pair = TokenService.issue_pair(user=fan)
    Session.objects.filter(pk=pair.session.pk).update(auth_level=AUTH_LEVEL_STEP_UP)

    request = request_with(pair.access)
    auth.authenticate(request)

    assert request.auth_level == AUTH_LEVEL_STEP_UP


def test_a_role_changed_in_the_database_takes_effect_immediately(auth, fan, roles):
    """
    **Le claim `role` n autorise rien.**

    Il voyage dans le jeton pour le client — afficher le bon menu sans un appel
    supplementaire. La decision d autorisation, elle, lit `user.role_id` sur
    l utilisateur charge depuis la base. Sans cette separation, promouvoir ou
    RETROGRADER un compte n aurait d effet qu au rafraichissement suivant.
    """
    pair = TokenService.issue_pair(user=fan)
    User.objects.filter(pk=fan.pk).update(role=roles["ADMIN"])

    request = request_with(pair.access)
    resolved, claims = auth.authenticate(request)
    request.user = resolved

    assert claims["role"] == "FAN", "le jeton porte toujours l ancien role"
    assert subject_from_request(request).role == "ADMIN", "la base fait foi"

    decision = authorize(subject_from_request(request), Action.ORGANIZER_READ, Resource(organizer_id=None))
    assert decision.reason.value != "role_not_granted"


# ===========================================================================
# Absence et malformation de l en-tete
# ===========================================================================


def test_no_authorization_header_is_not_an_error(auth, db):
    """
    Un point de terminaison public — l inscription — n envoie aucun jeton. Lever
    ici les casserait tous.
    """
    assert auth.authenticate(factory.get("/api/v1/whatever")) is None


def test_another_scheme_is_left_to_the_other_authentication_classes(auth, db):
    assert auth.authenticate(request_with("dXNlcjpwYXNz", scheme="Basic")) is None


@pytest.mark.parametrize("header", ["Bearer", "Bearer a b", "Bearer  "])
def test_a_malformed_bearer_header_is_refused_rather_than_ignored(auth, db, header):
    """
    L intention d utiliser un jeton est claire, la forme ne l est pas. Retomber
    en anonyme donnerait un 403 incomprehensible la ou un 401 explicite est du.
    """
    request = factory.get("/api/v1/whatever", HTTP_AUTHORIZATION=header)

    with pytest.raises(TokenInvalidError):
        auth.authenticate(request)


@pytest.mark.parametrize("rubbish", ["abc", "a.b.c", "..", "x" * 200])
def test_a_token_that_is_not_a_token_is_refused(auth, db, rubbish):
    with pytest.raises(TokenInvalidError):
        auth.authenticate(request_with(rubbish))


def test_a_refresh_token_cannot_authenticate(auth, fan):
    """
    Sans le claim `token_type`, le jeton de sept jours deviendrait un jeton
    d acces permanent et la rotation entiere serait contournee.
    """
    pair = TokenService.issue_pair(user=fan)

    with pytest.raises(TokenInvalidError):
        auth.authenticate(request_with(pair.refresh))


# ===========================================================================
# Revocation immediate
# ===========================================================================


def test_a_revoked_session_is_refused_immediately(auth, fan):
    """
    **Le test qui justifie la requete SQL par appel.**

    Sans relecture de la session, un jeton vole resterait valable quinze minutes
    apres la detection du vol, et la table `session` ne servirait qu au
    rafraichissement.
    """
    pair = TokenService.issue_pair(user=fan)
    assert auth.authenticate(request_with(pair.access)) is not None

    TokenService.revoke_session(pair.session, SESSION_REVOKED_LOGOUT)

    with pytest.raises(TokenInvalidError):
        auth.authenticate(request_with(pair.access))


def test_an_expired_session_is_refused_even_if_the_access_token_is_still_valid(auth, fan):
    """
    Les deux durees de vie sont independantes : la session expire avec le
    refresh (7 jours), l access dure 15 minutes. Une session forcee dans le
    passe doit fermer l acces sans attendre l expiration du jeton.
    """
    pair = TokenService.issue_pair(user=fan)
    Session.objects.filter(pk=pair.session.pk).update(expires_at=timezone.now() - datetime.timedelta(days=1))

    with pytest.raises(TokenInvalidError):
        auth.authenticate(request_with(pair.access))


@pytest.mark.parametrize("field", ["is_active", "anonymized_at"])
def test_a_deactivated_or_anonymised_account_loses_access_at_once(auth, fan, field):
    pair = TokenService.issue_pair(user=fan)
    value = False if field == "is_active" else timezone.now()
    User.objects.filter(pk=fan.pk).update(**{field: value})

    with pytest.raises(TokenInvalidError):
        auth.authenticate(request_with(pair.access))


def test_an_unknown_or_malformed_session_identifier_is_refused(auth, fan):
    pair = TokenService.issue_pair(user=fan)
    Session.objects.filter(pk=pair.session.pk).delete()

    with pytest.raises(TokenInvalidError):
        auth.authenticate(request_with(pair.access))


# ===========================================================================
# Appareil
# ===========================================================================


def test_a_token_presented_from_another_device_is_refused(auth, binding, fan):
    """
    401 et non 403 : un jeton valide presente depuis un autre appareil est un
    jeton probablement vole. La bonne reponse est « cette identite n est pas
    prouvee ».
    """
    device = binding.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    assert device is not None
    pair = TokenService.issue_pair(user=fan, device=device)
    assert auth.authenticate(request_with(pair.access)) is not None

    stolen = TokenService.issue_pair(user=fan)  # emis sans `did`

    with pytest.raises(DeviceMismatchError):
        auth.authenticate(request_with(stolen.access))


def test_an_exempt_role_authenticates_without_any_device(roles, auth):
    """ADR-03 : organisateurs et administrateurs n ont pas d appareil lie."""
    organizer = make_user(roles, role="ORGANIZER")
    pair = TokenService.issue_pair(user=organizer)

    resolved, _ = auth.authenticate(request_with(pair.access))

    assert resolved.pk == organizer.pk


def test_the_device_identifier_is_verified_against_the_lock_not_the_token(auth, binding, fan):
    """
    Le jeton PORTE `did`, il ne le decide pas. Revoquer l appareil doit fermer
    l acces des la requete suivante, sans attendre l expiration du jeton.
    """
    device = binding.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    assert device is not None
    pair = TokenService.issue_pair(user=fan, device=device)

    binding.revoke(device, "USER_RESET")

    with pytest.raises(DeviceMismatchError):
        auth.authenticate(request_with(pair.access))


def test_the_challenge_header_names_the_expected_scheme(auth):
    assert auth.authenticate_header(None) == 'Bearer realm="api"'


def test_two_users_never_share_a_session(auth, roles):
    """
    Garde-fou : le `sid` d un jeton ne doit jamais resoudre l utilisateur d un
    autre. C est la faille multi-comptes classique quand la session est
    retrouvee par un identifiant fourni par le client.
    """
    first = make_user(roles, email="premier-auth@example.test")
    second = make_user(roles, email="second-auth@example.test")
    pair = TokenService.issue_pair(user=first)

    resolved, _ = auth.authenticate(request_with(pair.access))

    assert resolved.pk == first.pk
    assert resolved.pk != second.pk
    assert uuid.UUID(str(pair.session.pk)) == pair.session.pk
