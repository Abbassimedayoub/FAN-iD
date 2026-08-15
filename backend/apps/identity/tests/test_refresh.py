"""
Rafraichissement : rotation, reutilisation, empreinte.

Le test qui porte le lot est
`test_a_refused_fingerprint_leaves_the_token_usable`. Tous les autres
passeraient avec une implementation qui tourne le jeton AVANT de verifier
l appareil — et cette implementation transformerait chaque refus en
deconnexion definitive, y compris pour un client legitime qui a simplement
oublie d envoyer son empreinte.
"""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.identity.constants import DEVICE_REVOKED_USER_RESET, PLATFORM_ANDROID
from apps.identity.exceptions import DeviceMismatchError
from apps.identity.models import Device, Session, User
from apps.identity.services.authentication import AuthenticationService, LoginCommand, RefreshCommand
from apps.identity.services.devices import DeviceBindingService
from apps.identity.constants import SESSION_REVOKED_ROTATION_REUSE
from apps.identity.services.tokens import TokenService
from apps.identity.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    TokenReuseDetectedError,
    TokenType,
    decode_token,
)

PASSWORD = "Chataigne-Orageuse-2026"
PHONE = "a" * 64
TABLET = "b" * 64


@pytest.fixture
def binding() -> DeviceBindingService:
    return DeviceBindingService(lock=FakeDeviceLock())


@pytest.fixture
def service(binding) -> AuthenticationService:
    return AuthenticationService(binding=binding)


def make_user(roles, role: str = "FAN", email: str = "supporter@example.test") -> User:
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1996, 5, 4),
        terms_accepted_at=timezone.now(),
        role=roles[role],
    )


@pytest.fixture
def fan(db, roles) -> User:
    return make_user(roles)


def login(service, **overrides):
    values: dict = {"email": "supporter@example.test", "password": PASSWORD}
    values.update(overrides)
    return service.login(LoginCommand(**values))


# ===========================================================================
# L invariant du lot : un refus ne consomme pas le jeton
# ===========================================================================


def test_a_refused_fingerprint_leaves_the_token_usable(service, fan):
    """
    **Le test qui porte le lot.**

    Verifier l appareil APRES la rotation consommerait le refresh avant de le
    refuser : le porteur legitime qui oublie son empreinte se retrouverait
    deconnecte pour de bon, sans recours autre qu une reconnexion complete.

    Le jeton doit donc survivre intact a un refus.
    """
    opened = login(service, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    with pytest.raises(DeviceMismatchError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh, fingerprint=TABLET))

    # Le meme jeton, avec la bonne empreinte, doit toujours fonctionner.
    rotated = service.refresh(RefreshCommand(refresh=opened.pair.refresh, fingerprint=PHONE))
    assert rotated.pair.refresh != opened.pair.refresh


def test_a_refused_fingerprint_does_not_revoke_the_family(service, fan):
    """Un refus d appareil n est pas une reutilisation : la session reste ouverte."""
    opened = login(service, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    with pytest.raises(DeviceMismatchError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh, fingerprint=TABLET))

    session = Session.objects.get(pk=opened.pair.session.pk)
    assert session.revoked_at is None


# ===========================================================================
# Rotation nominale
# ===========================================================================


def test_a_valid_refresh_returns_a_new_pair(service, fan):
    opened = login(service)

    rotated = service.refresh(RefreshCommand(refresh=opened.pair.refresh))

    assert rotated.pair.access != opened.pair.access
    assert rotated.pair.refresh != opened.pair.refresh
    assert rotated.user.pk == fan.pk


def test_the_rotation_keeps_the_same_session_and_family(service, fan):
    """
    La rotation PROLONGE une session, elle n en ouvre pas une nouvelle. Creer
    une ligne par rotation ferait croitre `identity_session` d une ligne toutes
    les quinze minutes et par utilisateur.
    """
    opened = login(service)

    rotated = service.refresh(RefreshCommand(refresh=opened.pair.refresh))

    assert rotated.pair.session.pk == opened.pair.session.pk
    assert rotated.pair.session.family_id == opened.pair.session.family_id
    assert Session.objects.count() == 1


def test_the_old_refresh_stops_working_after_rotation(service, fan):
    """Usage unique strict : rejouer l ancien jeton est une reutilisation."""
    opened = login(service)
    service.refresh(RefreshCommand(refresh=opened.pair.refresh))

    with pytest.raises(TokenReuseDetectedError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh))


def test_the_new_access_carries_the_same_session(service, fan):
    opened = login(service)

    rotated = service.refresh(RefreshCommand(refresh=opened.pair.refresh))

    claims = decode_token(rotated.pair.access, expected_type=TokenType.ACCESS)
    assert claims["sid"] == str(opened.pair.session.pk)


# ===========================================================================
# Reutilisation
# ===========================================================================


def test_replaying_a_rotated_refresh_revokes_the_whole_family(service, fan):
    """
    On ne sait pas lequel des deux porteurs est l attaquant : celui qui rejoue
    peut etre le voleur comme la victime. Deconnecter les deux est le seul
    choix sur (RFC 6819 s5.2.2.3).
    """
    opened = login(service)
    service.refresh(RefreshCommand(refresh=opened.pair.refresh))

    with pytest.raises(TokenReuseDetectedError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh))

    session = Session.objects.get(pk=opened.pair.session.pk)
    assert session.revoked_at is not None
    assert session.revoked_reason == SESSION_REVOKED_ROTATION_REUSE


def test_the_revocation_survives_the_refusal(service, fan):
    """
    La revocation s execute HORS de la transaction de rotation. Placee dedans,
    elle serait annulee par la remontee de l exception — le controle passerait
    au vert pendant que la famille resterait vivante.
    """
    opened = login(service)
    rotated = service.refresh(RefreshCommand(refresh=opened.pair.refresh))

    with pytest.raises(TokenReuseDetectedError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh))

    # Le jeton COURANT, pourtant legitime, est mort avec la famille.
    with pytest.raises(TokenInvalidError):
        service.refresh(RefreshCommand(refresh=rotated.pair.refresh))


# ===========================================================================
# Empreinte d appareil
# ===========================================================================


def test_a_refresh_from_the_bound_device_passes(service, fan):
    opened = login(service, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    rotated = service.refresh(RefreshCommand(refresh=opened.pair.refresh, fingerprint=PHONE))

    assert rotated.device is not None
    assert rotated.device.pk == opened.device.pk


def test_a_refresh_without_the_fingerprint_is_refused(service, fan):
    """
    Sans cette exigence, le verrou d appareil ne protegerait que l instant de la
    connexion : un refresh exfiltre fonctionnerait de n importe ou.
    """
    opened = login(service, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    with pytest.raises(DeviceMismatchError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh))


def test_a_refresh_with_a_wrong_fingerprint_is_refused(service, fan):
    opened = login(service, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    with pytest.raises(DeviceMismatchError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh, fingerprint=TABLET))


def test_a_malformed_fingerprint_gives_401_and_not_500(service, fan):
    """
    `compare_digest` leve `TypeError` sur une chaine non ASCII. Comparee telle
    quelle, une empreinte exotique produirait une 500 la ou un 401 est du.
    """
    opened = login(service, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    with pytest.raises(DeviceMismatchError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh, fingerprint="empreinte-\u00e9\u00e0"))


def test_a_revoked_device_blocks_the_refresh(service, binding, fan):
    """
    Sans ce controle, revoquer un appareil n empecherait pas la session ouverte
    de se prolonger de rotation en rotation jusqu a l expiration du refresh.
    """
    opened = login(service, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    binding.revoke(opened.device, DEVICE_REVOKED_USER_RESET)

    with pytest.raises(DeviceMismatchError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh, fingerprint=PHONE))


def test_a_session_without_device_needs_no_fingerprint(service, fan):
    """Un supporter sur navigateur n a pas d empreinte stable a fournir."""
    opened = login(service)

    rotated = service.refresh(RefreshCommand(refresh=opened.pair.refresh))

    assert rotated.device is None


def test_an_exempt_role_needs_no_fingerprint(service, roles):
    """ADR-03 : un organisateur travaille depuis plusieurs postes."""
    organizer = make_user(roles, role="ORGANIZER", email="organisateur@example.test")
    opened = login(service, email=organizer.email, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    rotated = service.refresh(RefreshCommand(refresh=opened.pair.refresh))

    assert rotated.device is None


# ===========================================================================
# Jetons refuses
# ===========================================================================


def test_an_access_token_presented_as_a_refresh_is_refused(service, fan):
    """
    Confusion de type — le piege le plus grave de la famille JWT : il
    contournerait la rotation entiere.
    """
    opened = login(service)

    with pytest.raises(TokenInvalidError):
        service.refresh(RefreshCommand(refresh=opened.pair.access))


def test_a_forged_refresh_is_refused(service, fan):
    with pytest.raises(TokenInvalidError):
        service.refresh(RefreshCommand(refresh="pas.un.jeton"))


def test_a_revoked_session_cannot_be_refreshed(service, fan):
    opened = login(service)
    TokenService.revoke_session(opened.pair.session, "LOGOUT")

    with pytest.raises(TokenInvalidError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh))


def test_an_expired_refresh_is_refused(service, fan):
    """
    `TOKEN_EXPIRED` et non `TOKEN_INVALID` : le client doit savoir qu il faut se
    reconnecter, et l information ne sert a rien a un attaquant — un jeton
    expire est un jeton qu il possede deja.
    """
    opened = login(service)
    past = timezone.now() - datetime.timedelta(days=40)
    stale = TokenService.issue_pair(user=fan, now=past)

    with pytest.raises(TokenExpiredError):
        service.refresh(RefreshCommand(refresh=stale.refresh))

    assert opened.pair.refresh  # le jeton frais n a pas ete touche


def test_a_device_revoked_behind_the_cache_is_still_refused(service, fan):
    """
    Revocation ecrite DIRECTEMENT en base, sans passer par le service — donc
    sans liberer le verrou en cache. Le controle doit lire l etat reel de la
    ligne et non se fier au cache, sinon une revocation appliquee par une
    commande d administration resterait sans effet jusqu a expiration du verrou.
    """
    opened = login(service, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    Device.objects.filter(pk=opened.device.pk).update(
        revoked_at=timezone.now(), revoked_reason=DEVICE_REVOKED_USER_RESET
    )

    with pytest.raises(DeviceMismatchError):
        service.refresh(RefreshCommand(refresh=opened.pair.refresh, fingerprint=PHONE))
