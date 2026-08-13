"""
Connexion : l ordre des controles, et l absence d oracle.

Le test qui porte le lot est
`test_a_wrong_password_on_a_locked_account_never_reveals_the_lock`. Tous les
autres pourraient passer avec une implementation qui verifie l appareil AVANT le
mot de passe — et cette implementation offrirait a un attaquant un oracle
d existence parfait, sans deviner un seul mot de passe.
"""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.core.outbox.models import OutboxEvent
from apps.identity.constants import PLATFORM_ANDROID, PLATFORM_IOS
from apps.identity.events import USER_LOGGED_IN
from apps.identity.exceptions import DeviceLockedError, InvalidCredentialsError
from apps.identity.models import Session, User
from apps.identity.services.authentication import AuthenticationService, LoginCommand
from apps.identity.services.devices import DeviceBindingService
from apps.identity.tokens import TokenType, decode_token

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


def command(**overrides) -> LoginCommand:
    values: dict = {"email": "supporter@example.test", "password": PASSWORD}
    values.update(overrides)
    return LoginCommand(**values)


# ===========================================================================
# L invariant du lot : identifiants d abord, appareil ensuite
# ===========================================================================


def test_a_wrong_password_on_a_locked_account_never_reveals_the_lock(service, binding, fan):
    """
    **Le test qui porte le lot.**

    Un compte verrouille sur un autre appareil, un mot de passe faux : la
    reponse doit etre `401 INVALID_CREDENTIALS`, jamais `403 DEVICE_LOCKED`.

    Verifier l appareil en premier donnerait a l attaquant un oracle parfait :
    403 sur une adresse existante et verrouillee, 401 sur une adresse inconnue.
    Il enumererait tous les comptes sans deviner un seul mot de passe.
    """
    binding.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    with pytest.raises(InvalidCredentialsError) as caught:
        service.login(command(password="Faux-Mot-De-Passe-2026", fingerprint=TABLET, platform=PLATFORM_IOS))

    assert caught.value.status_code == 401
    assert caught.value.code == "INVALID_CREDENTIALS"


def test_the_lock_is_revealed_only_once_the_password_is_proven(service, binding, fan):
    """Le pendant du test precedent : le bon mot de passe donne bien 403."""
    binding.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    with pytest.raises(DeviceLockedError) as caught:
        service.login(command(fingerprint=TABLET, platform=PLATFORM_IOS))

    assert caught.value.status_code == 403
    assert caught.value.details["reset_available"] is True


# ===========================================================================
# Anti-enumeration : le corps ET le temps
# ===========================================================================


@pytest.mark.django_db
def test_an_unknown_address_and_a_wrong_password_are_indistinguishable(service, roles):
    make_user(roles)

    with pytest.raises(InvalidCredentialsError) as unknown:
        service.login(command(email="jamais-inscrit@example.test"))
    with pytest.raises(InvalidCredentialsError) as wrong:
        service.login(command(password="Faux-Mot-De-Passe-2026"))

    assert unknown.value.code == wrong.value.code
    assert unknown.value.message == wrong.value.message
    assert unknown.value.details == wrong.value.details == {}


def test_an_unknown_address_still_pays_the_price_of_a_hash(service, roles, monkeypatch):
    """
    Un corps identique ne suffit pas : sans hachage factice, une adresse
    inconnue repondrait en une milliseconde la ou une adresse connue coute le
    temps d Argon2id. La difference se mesure depuis l exterieur.

    On compte l APPEL plutot que le temps : un test chronometre serait instable
    sur une machine chargee, et l environnement de test installe de toute facon
    un hacheur rapide qui rendrait la mesure vide de sens.
    """
    calls: list[str] = []
    import apps.identity.services.authentication as module

    def record(raw: str, encoded: str) -> bool:
        calls.append(encoded)
        return False

    monkeypatch.setattr(module, "check_password", record)

    with pytest.raises(InvalidCredentialsError):
        service.login(command(email="jamais-inscrit@example.test"))

    assert len(calls) == 1, "le hachage factice doit etre verifie meme sans compte"


@pytest.mark.parametrize("field", ["is_active", "anonymized_at"])
def test_a_deactivated_account_is_refused_without_saying_so(service, fan, field):
    """
    Un motif distinct confirmerait que l adresse existe — et qu on a devine le
    mot de passe, ce qui est encore pire.
    """
    value = False if field == "is_active" else timezone.now()
    User.objects.filter(pk=fan.pk).update(**{field: value})

    with pytest.raises(InvalidCredentialsError) as caught:
        service.login(command())

    assert caught.value.code == "INVALID_CREDENTIALS"


def test_the_address_is_matched_regardless_of_case(service, fan):
    """`citext` (lot S1-A.1a) : aucun `LOWER()`, l index unique reste utilisable."""
    result = service.login(command(email="Supporter@Example.TEST"))

    assert result.user.pk == fan.pk


# ===========================================================================
# Chemin nominal
# ===========================================================================


def test_a_successful_login_opens_a_session_and_issues_a_pair(service, fan):
    result = service.login(command(ip="203.0.113.7", user_agent="Dalvik/2.1"))

    session = Session.objects.get(pk=result.pair.session.pk)
    assert session.user_id == fan.pk
    assert session.ip == "203.0.113.7"
    assert session.user_agent == "Dalvik/2.1"
    assert decode_token(result.pair.access, expected_type=TokenType.ACCESS)["sid"] == str(session.pk)


def test_a_login_without_any_fingerprint_binds_no_device(service, fan):
    """
    Un supporter qui se connecte depuis un navigateur n a pas d empreinte stable
    a fournir. Lui en exiger une reviendrait a inventer une donnee que le client
    ne peut pas produire — et l IP ou le `User-Agent` ne sont pas des
    substituts acceptables.
    """
    result = service.login(command())

    assert result.device is None
    assert decode_token(result.pair.access, expected_type=TokenType.ACCESS)["did"] is None


def test_the_same_device_logs_in_again_without_creating_a_second_row(service, fan):
    first = service.login(command(fingerprint=PHONE, platform=PLATFORM_ANDROID))
    second = service.login(command(fingerprint=PHONE, platform=PLATFORM_ANDROID))

    assert first.device is not None
    assert second.device is not None
    assert first.device.pk == second.device.pk
    assert first.pair.session.family_id != second.pair.session.family_id


def test_an_exempt_role_ignores_the_fingerprint_it_sends(service, roles):
    """ADR-03 : un organisateur travaille depuis plusieurs postes."""
    organizer = make_user(roles, role="ORGANIZER", email="organisateur@example.test")

    result = service.login(command(email=organizer.email, fingerprint=PHONE, platform=PLATFORM_ANDROID))

    assert result.device is None


# ===========================================================================
# Evenement
# ===========================================================================


def test_a_successful_login_publishes_one_event_without_personal_data(service, fan):
    service.login(command())

    events = list(OutboxEvent.objects.filter(event_type=USER_LOGGED_IN))
    assert len(events) == 1
    assert events[0].payload == {"role": "FAN", "device_bound": False}
    assert "example.test" not in str(events[0].payload)


def test_a_refused_login_publishes_nothing(service, fan):
    """
    L evenement vit dans la transaction de la connexion. Un `user.logged_in`
    emis sur un echec declencherait une alerte de connexion sur un compte ou
    personne ne s est connecte — exactement le message qui pousse un utilisateur
    a changer un mot de passe qui n a pas fuite.
    """
    with pytest.raises(InvalidCredentialsError):
        service.login(command(password="Faux-Mot-De-Passe-2026"))

    assert not OutboxEvent.objects.filter(event_type=USER_LOGGED_IN).exists()
    assert not Session.objects.exists()


def test_a_login_blocked_by_the_device_lock_leaves_no_session_behind(service, binding, fan):
    """
    La liaison d appareil et l emission des jetons partagent une transaction :
    un refus a l etape appareil ne doit laisser ni session, ni evenement.
    """
    binding.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    with pytest.raises(DeviceLockedError):
        service.login(command(fingerprint=TABLET, platform=PLATFORM_IOS))

    assert not Session.objects.exists()
    assert not OutboxEvent.objects.filter(event_type=USER_LOGGED_IN).exists()
