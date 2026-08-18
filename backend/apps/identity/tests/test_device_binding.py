"""
Liaison d appareil : un seul appareil actif, et aucune panne qui ouvre l acces.

Le test decisif est `test_binding_still_works_when_redis_is_down` : il simule la
panne par un backend qui LEVE, plutot qu en arretant un conteneur. C est plus
fiable — pas de conteneur a redemarrer, pas de test qui echoue selon l ordre
d execution — et strictement equivalent du point de vue du service, qui ne voit
de Redis que les exceptions qu il produit.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from django.utils import timezone

from apps.core.adapters.device_lock import FakeDeviceLock
from apps.core.interfaces import DeviceLockBackend
from apps.identity.constants import DEVICE_REVOKED_USER_RESET, PLATFORM_ANDROID, PLATFORM_IOS
from apps.identity.exceptions import DeviceLockedError, DeviceMismatchError, InvalidFingerprintError
from apps.identity.locks import PostgresDeviceLock, ResilientDeviceLock
from apps.identity.models import Device, User
from apps.identity.services.devices import LAST_SEEN_REFRESH, DeviceBindingService

PHONE = "a" * 64
TABLET = "b" * 64


def bound(device: Device | None) -> Device:
    """
    Restreint `Device | None` a `Device`.

    `bind()` et `assert_matches()` renvoient `None` pour les roles exemptes du
    verrou (ADR-03). Ce n est donc pas une precaution de typage : le `None` est
    un cas metier reel, et l assertion dit explicitement qu on ne l attend PAS
    ici. Un `# type: ignore` aurait masque la difference.
    """
    assert device is not None, "un appareil etait attendu, aucun n a ete lie"
    return device


class BrokenLock(DeviceLockBackend):
    """
    Redis injoignable : toute operation leve.

    `OSError` plutot que `redis.exceptions.RedisError` pour que le test ne
    depende pas de la presence du client Redis — les deux figurent dans
    `TRANSIENT_FAILURES`, et c est precisement ce que ce test doit prouver.
    """

    def acquire(self, *args, **kwargs):
        raise OSError("redis injoignable")

    def get_active(self, *args, **kwargs):
        raise OSError("redis injoignable")

    def release(self, *args, **kwargs):
        raise OSError("redis injoignable")


def make_user(roles, role="FAN", email=None) -> User:
    return User.objects.create_user(
        email=email or f"{role.lower()}-device@example.test",
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


@pytest.fixture
def service() -> DeviceBindingService:
    return DeviceBindingService(lock=FakeDeviceLock())


# ===========================================================================
# Format de l empreinte
# ===========================================================================


@pytest.mark.parametrize(
    ("bad", "why"),
    [
        ("A" * 64, "majuscules : deux representations d une meme empreinte"),
        ("a" * 63, "trop courte pour un SHA-256"),
        ("a" * 65, "trop longue"),
        ("z" * 64, "caracteres non hexadecimaux"),
        ("", "vide"),
        ("  " + "a" * 62, "espaces"),
    ],
)
def test_a_malformed_fingerprint_is_refused(service, bad, why):
    """
    On REFUSE plutot que de normaliser.

    Mettre l empreinte en minuscules a la volee masquerait un client qui envoie
    n importe quoi — et le jour ou ce client changera de forme, le probleme
    apparaitra ailleurs, sans lien apparent.
    """
    with pytest.raises(InvalidFingerprintError):
        service.validate_fingerprint(bad)


def test_a_canonical_fingerprint_is_accepted(service):
    assert service.validate_fingerprint(PHONE) == PHONE


@pytest.mark.django_db
def test_an_unknown_platform_is_refused_with_the_allowed_values(service, fan):
    with pytest.raises(InvalidFingerprintError) as caught:
        service.bind(user=fan, fingerprint=PHONE, platform="symbian")

    assert set(caught.value.details["platform"]) == {"android", "ios", "web"}
    assert not Device.objects.exists()


# ===========================================================================
# Liaison
# ===========================================================================


@pytest.mark.django_db
def test_the_first_device_is_bound(service, fan):
    device = service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID, label="Pixel 8")

    assert device is not None
    assert device.fingerprint == PHONE
    assert device.revoked_at is None
    assert Device.objects.active().for_user(fan).count() == 1


@pytest.mark.django_db
def test_binding_the_same_device_twice_does_not_create_a_second_row(service, fan):
    first = service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    second = service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    assert first.pk == second.pk
    assert Device.objects.count() == 1


@pytest.mark.django_db
def test_a_second_device_is_refused_with_enough_detail_to_be_recognised(service, fan):
    """
    Le corps du refus doit permettre a l utilisateur de reconnaitre son ancien
    telephone — sinon le message est inutilisable — sans renseigner quelqu un
    qui viendrait de prouver le mot de passe d autrui. D ou le libelle tronque.
    """
    service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID, label="Pixel 8 de Ines")

    with pytest.raises(DeviceLockedError) as caught:
        service.bind(user=fan, fingerprint=TABLET, platform=PLATFORM_IOS)

    details = caught.value.details
    assert details["reset_available"] is True
    assert details["active_device_label"] == "Pixel 8 de I…"
    assert "bound_at" in details
    assert caught.value.status_code == 403
    assert Device.objects.count() == 1


@pytest.mark.django_db
def test_a_revoked_device_frees_the_slot(service, fan):
    """
    L unicite est PARTIELLE : elle ne porte que sur les appareils actifs.
    L historique reste, ce qui permet l audit d une rotation d appareils.
    """
    first = service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    service.revoke(first, DEVICE_REVOKED_USER_RESET)

    second = service.bind(user=fan, fingerprint=TABLET, platform=PLATFORM_IOS)

    assert second.pk != first.pk
    assert Device.objects.count() == 2
    assert Device.objects.active().count() == 1
    assert Device.objects.get(pk=first.pk).revoked_reason == DEVICE_REVOKED_USER_RESET


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["ORGANIZER", "ADMIN"])
def test_the_exempt_roles_are_never_bound_to_a_device(roles, service, role):
    """
    ADR-03. Un organisateur travaille depuis un poste fixe, un telephone, et
    parfois la machine d un collaborateur : lui imposer un appareil unique
    transformerait chaque changement de poste en parcours de reinitialisation.
    """
    user = make_user(roles, role=role)

    assert service.bind(user=user, fingerprint=PHONE, platform=PLATFORM_ANDROID) is None
    assert service.assert_matches(user=user, device_id=None) is None
    assert not Device.objects.exists()


# ===========================================================================
# Ecriture paresseuse de `last_seen_at`
# ===========================================================================


@pytest.mark.django_db
def test_last_seen_is_not_rewritten_on_every_request(service, fan):
    """
    Sans cette paresse, CHAQUE requete de l API produirait une ecriture sur
    `identity_device`. Au pic de connexions — l ouverture des portes — c est la
    base qui sature, pour une donnee dont personne ne lit la minute exacte.
    """
    device = service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    original = Device.objects.get(pk=device.pk).last_seen_at

    service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    assert Device.objects.get(pk=device.pk).last_seen_at == original


@pytest.mark.django_db
def test_last_seen_is_refreshed_once_the_delay_has_passed(service, fan):
    device = service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    later = timezone.now() + LAST_SEEN_REFRESH + datetime.timedelta(minutes=1)

    service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID, now=later)

    assert Device.objects.get(pk=device.pk).last_seen_at >= later


# ===========================================================================
# Verification a chaque requete
# ===========================================================================


@pytest.mark.django_db
def test_the_bound_device_is_accepted_and_any_other_is_refused(service, fan):
    device = service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    assert bound(service.assert_matches(user=fan, device_id=device.pk)).pk == device.pk

    for wrong in (uuid.uuid4(), None, "pas-un-uuid"):
        with pytest.raises(DeviceMismatchError):
            service.assert_matches(user=fan, device_id=wrong)


@pytest.mark.django_db
def test_a_mismatched_device_is_a_401_not_a_403(service, fan):
    """
    Un jeton presente depuis un autre appareil est un jeton probablement vole.
    La bonne reponse est « cette identite n est pas prouvee », pas « vous n avez
    pas le droit » : c est un probleme d authentification, pas d autorisation.
    """
    service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    with pytest.raises(DeviceMismatchError) as caught:
        service.assert_matches(user=fan, device_id=uuid.uuid4())

    assert caught.value.status_code == 401
    assert caught.value.code == "DEVICE_MISMATCH"


@pytest.mark.django_db
def test_an_empty_cache_authorizes_nothing_by_itself(fan):
    """
    Cache froid : le service relit la verite en base. Un verrou absent ne doit
    JAMAIS valoir autorisation — c est la forme la plus courante du fail-open.
    """
    service = DeviceBindingService(lock=FakeDeviceLock())
    device = bound(service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID))

    cold = DeviceBindingService(lock=FakeDeviceLock())
    assert bound(cold.assert_matches(user=fan, device_id=device.pk)).pk == device.pk
    with pytest.raises(DeviceMismatchError):
        cold.assert_matches(user=fan, device_id=uuid.uuid4())


@pytest.mark.django_db
def test_a_user_without_any_device_matches_nothing(service, fan):
    with pytest.raises(DeviceMismatchError):
        service.assert_matches(user=fan, device_id=uuid.uuid4())


# ===========================================================================
# Panne de Redis — jamais fail-open
# ===========================================================================


@pytest.mark.django_db
def test_binding_still_works_when_redis_is_down(fan):
    """
    Redis n est qu un cache de decision : sa panne coute une requete SQL, pas un
    droit. La verite reste `UNIQUE(user_id) WHERE revoked_at IS NULL`.
    """
    degraded = DeviceBindingService(
        lock=ResilientDeviceLock(primary=BrokenLock(), fallback=PostgresDeviceLock())
    )

    device = degraded.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    assert device is not None
    assert bound(degraded.assert_matches(user=fan, device_id=device.pk)).pk == device.pk


@pytest.mark.django_db
def test_a_redis_outage_never_opens_the_lock(fan):
    """
    Le test qui compte. Redis muet, un appareil deja lie : un SECOND appareil
    doit toujours etre refuse.

    Le chemin le plus tentant a coder — `except: return True` — passerait tous
    les tests nominaux et ouvrirait le compte a n importe quel appareil le jour
    d une panne.
    """
    degraded = DeviceBindingService(
        lock=ResilientDeviceLock(primary=BrokenLock(), fallback=PostgresDeviceLock())
    )
    degraded.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)

    with pytest.raises(DeviceLockedError):
        degraded.bind(user=fan, fingerprint=TABLET, platform=PLATFORM_IOS)

    with pytest.raises(DeviceMismatchError):
        degraded.assert_matches(user=fan, device_id=uuid.uuid4())


def test_when_the_fallback_fails_too_the_error_propagates():
    """
    Fail-closed jusqu au bout : si les deux backends tombent, l exception
    remonte, la requete part en erreur et l acces est refuse. Renvoyer `True`
    « pour ne pas bloquer les utilisateurs » serait exactement la mauvaise
    reponse.
    """
    doomed = ResilientDeviceLock(primary=BrokenLock(), fallback=BrokenLock())

    with pytest.raises(OSError):
        doomed.acquire("user", "device", 60)
    with pytest.raises(OSError):
        doomed.get_active("user")


# ===========================================================================
# Le repli PostgreSQL, isole
# ===========================================================================


@pytest.mark.django_db
def test_the_postgres_lock_reads_the_single_source_of_truth(service, fan):
    device = service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    lock = PostgresDeviceLock()

    assert lock.get_active(str(fan.pk)) == str(device.pk)
    assert lock.acquire(str(fan.pk), str(device.pk), 60) is True
    assert lock.acquire(str(fan.pk), str(uuid.uuid4()), 60) is False


@pytest.mark.django_db
def test_releasing_the_postgres_lock_does_not_unbind_anything(service, fan):
    """
    `release()` est sans effet, deliberement : liberer le verrou signifierait
    revoquer l appareil, une operation metier qui exige un motif et laisse une
    trace. Un `release()` silencieux offrirait un chemin de deliaison sans l un
    ni l autre.
    """
    device = service.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    lock = PostgresDeviceLock()

    lock.release(str(fan.pk))

    assert Device.objects.get(pk=device.pk).revoked_at is None
    assert lock.get_active(str(fan.pk)) == str(device.pk)
