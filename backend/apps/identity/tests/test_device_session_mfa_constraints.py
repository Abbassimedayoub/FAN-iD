"""
Invariants de `Device`, `Session` et `MfaChallenge`, prouvés au niveau du SGBD.

Chaque contrainte est éprouvée par une **insertion SQL directe** (plan S1 §7.3) :
un test qui passerait par l'ORM ne prouverait que la validation applicative,
alors que l'intérêt d'une contrainte en base est de tenir quand l'application
est contournée — script d'administration, migration de données, injection.
"""

import datetime
import uuid

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.utils import DataError
from django.utils import timezone

from apps.identity.constants import (
    AUTH_LEVEL_PASSWORD,
    DEVICE_REVOKED_USER_RESET,
    MFA_PURPOSE_DEVICE_RESET,
    OTP_MAX_ATTEMPTS,
    PLATFORM_ANDROID,
)
from apps.identity.models import Device, MfaChallenge, Session, User

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("roles")]

VALID_FINGERPRINT = "a" * 64
VALID_CODE_HASH = "f" * 64


@pytest.fixture
def fan():
    return User.objects.create_user(
        email="device-owner@example.test",
        password="irrelevant-here-x9",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
    )


def _insert_device_sql(
    user, fingerprint=VALID_FINGERPRINT, platform=PLATFORM_ANDROID, revoked_at=None, revoked_reason=None
):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO identity_device
                (id, user_id, fingerprint, label, platform, bound_at, last_seen_at,
                 revoked_at, revoked_reason)
            VALUES (%s, %s, %s, %s, %s, now(), now(), %s, %s)
            """,
            [uuid.uuid4(), user.id, fingerprint, "Appareil", platform, revoked_at, revoked_reason],
        )


def _insert_mfa_sql(
    user,
    code_hash=VALID_CODE_HASH,
    purpose=MFA_PURPOSE_DEVICE_RESET,
    attempts=0,
    max_attempts=OTP_MAX_ATTEMPTS,
):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO identity_mfa_challenge
                (id, user_id, purpose, code_hash, attempts, max_attempts,
                 expires_at, consumed_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, now() + interval '5 minutes', NULL, now())
            """,
            [uuid.uuid4(), user.id, purpose, code_hash, attempts, max_attempts],
        )


# ============================================================ Device


def test_only_one_active_device_per_account(fan):
    """
    RM-5, garanti par une unicité PARTIELLE. Le cycle complet est vérifié :
    un actif, plusieurs révoqués coexistent, un second actif est refusé.
    """
    _insert_device_sql(fan)
    _insert_device_sql(
        fan, fingerprint="b" * 64, revoked_at=timezone.now(), revoked_reason=DEVICE_REVOKED_USER_RESET
    )
    _insert_device_sql(
        fan, fingerprint="c" * 64, revoked_at=timezone.now(), revoked_reason=DEVICE_REVOKED_USER_RESET
    )
    assert Device.objects.for_user(fan).active().count() == 1
    assert Device.objects.for_user(fan).revoked().count() == 2

    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_device_sql(fan, fingerprint="d" * 64)


def test_a_revoked_device_frees_the_slot_for_a_new_one(fan):
    """Le parcours de réinitialisation dépend de ce comportement."""
    _insert_device_sql(fan)
    Device.objects.for_user(fan).active().update(
        revoked_at=timezone.now(), revoked_reason=DEVICE_REVOKED_USER_RESET
    )
    _insert_device_sql(fan, fingerprint="e" * 64)
    assert Device.objects.for_user(fan).active().count() == 1
    assert Device.objects.for_user(fan).count() == 2


@pytest.mark.parametrize(
    ("fingerprint", "raison"),
    [
        ("A" * 64, "majuscules : deux representations du meme appareil"),
        ("a" * 63, "trop court pour un SHA-256"),
        ("z" * 64, "caracteres non hexadecimaux"),
        ("", "vide"),
    ],
)
def test_database_rejects_a_malformed_fingerprint(fan, fingerprint, raison):
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_device_sql(fan, fingerprint=fingerprint)


def test_a_fingerprint_longer_than_the_column_is_rejected_by_the_type(fan):
    """
    Garantie par le TYPE `varchar(64)`, pas par la contrainte CHECK.

    La distinction compte : PostgreSQL lève ici « value too long for type
    character varying(64) », que Django traduit en `DataError` et non en
    `IntegrityError`. Attendre indifféremment l'une ou l'autre masquerait
    laquelle des deux protections a réellement joué — et donc si l'on peut
    retirer le CHECK sans conséquence.
    """
    with pytest.raises(DataError), transaction.atomic():
        _insert_device_sql(fan, fingerprint="a" * 65)


def test_database_rejects_an_unknown_platform(fan):
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_device_sql(fan, platform="symbian")


def test_a_revoked_device_must_carry_a_reason(fan):
    """Une révocation sans motif perd toute valeur d'audit."""
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_device_sql(fan, revoked_at=timezone.now(), revoked_reason=None)


def test_a_revocation_reason_requires_a_revocation_date(fan):
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_device_sql(fan, revoked_at=None, revoked_reason=DEVICE_REVOKED_USER_RESET)


def test_deleting_a_user_removes_their_devices(fan):
    """L'empreinte est une donnee personnelle : la conserver serait un passif RGPD."""
    _insert_device_sql(fan)
    user_id = fan.id
    fan.delete()
    assert Device.objects.filter(user_id=user_id).count() == 0


# =========================================================== Session


def _make_session(fan, device=None, **kwargs):
    defaults = {
        "user": fan,
        "family_id": uuid.uuid4(),
        "device": device,
        "refresh_jti": uuid.uuid4(),
        "expires_at": timezone.now() + datetime.timedelta(days=7),
    }
    defaults.update(kwargs)
    return Session.objects.create(**defaults)


def test_refresh_jti_is_globally_unique(fan):
    """Deux sessions ne peuvent pas revendiquer le meme refresh courant."""
    jti = uuid.uuid4()
    _make_session(fan, refresh_jti=jti)
    with pytest.raises(IntegrityError), transaction.atomic():
        _make_session(fan, refresh_jti=jti)


def test_database_rejects_an_unknown_auth_level(fan):
    with pytest.raises(IntegrityError), transaction.atomic():
        _make_session(fan, auth_level=3)


def test_database_rejects_a_session_expiring_before_it_was_issued(fan):
    with pytest.raises(IntegrityError), transaction.atomic():
        _make_session(fan, expires_at=timezone.now() - datetime.timedelta(days=1))


def test_active_excludes_both_revoked_and_expired_sessions(fan):
    """
    Les deux conditions comptent. Ne filtrer que sur `revoked_at` laisserait
    passer une session expiree ; ne filtrer que sur `expires_at` laisserait
    passer une session revoquee pour reutilisation de jeton — le scenario de vol.
    """
    valid = _make_session(fan)
    _make_session(fan, revoked_at=timezone.now(), revoked_reason="LOGOUT")
    # Une session expirée s'obtient en antidatant l'ÉMISSION, pas en forçant
    # l'expiration dans le passé : `ck_session_expiry_after_issue` refuse — à
    # juste titre — une session qui expirerait avant d'avoir été émise.
    _make_session(
        fan,
        issued_at=timezone.now() - datetime.timedelta(days=8),
        expires_at=timezone.now() - datetime.timedelta(days=1),
    )

    assert list(Session.objects.for_user(fan).active()) == [valid]


def test_a_whole_family_can_be_revoked_at_once(fan):
    """Unite de reponse a une reutilisation de refresh (master prompt §17)."""
    family = uuid.uuid4()
    for _ in range(3):
        _make_session(fan, family_id=family)
    other = _make_session(fan)

    Session.objects.for_family(family).update(revoked_at=timezone.now(), revoked_reason="ROTATION_REUSE")
    assert Session.objects.for_family(family).active().count() == 0
    assert Session.objects.filter(pk=other.pk).active().count() == 1


def test_a_session_survives_the_purge_of_its_device(fan):
    """`SET_NULL` : la purge des appareils (Sprint 5) ne doit pas effacer l audit
    des sessions."""
    _insert_device_sql(fan)
    device = Device.objects.for_user(fan).active().get()
    session = _make_session(fan, device=device)
    device.delete()
    session.refresh_from_db()
    assert session.device_id is None


# ====================================================== MfaChallenge


def test_database_refuses_to_store_a_plaintext_code(fan):
    """
    Le garde-fou le plus important de cette table : `code_hash` doit etre un
    SHA-256. Un code a 6 chiffres ecrit tel quel est rejete par le SGBD.
    """
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_mfa_sql(fan, code_hash="042917")


def test_database_rejects_a_code_hash_that_is_not_hexadecimal(fan):
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_mfa_sql(fan, code_hash="z" * 64)


def test_attempts_can_never_exceed_the_cap(fan):
    _insert_mfa_sql(fan, attempts=OTP_MAX_ATTEMPTS)
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_mfa_sql(fan, attempts=OTP_MAX_ATTEMPTS + 1)


def test_database_rejects_an_unknown_purpose(fan):
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_mfa_sql(fan, purpose="WHATEVER")


def test_open_excludes_consumed_expired_and_exhausted_challenges(fan):
    """`open()` est la seule definition de « defi encore utilisable »."""
    usable = MfaChallenge.objects.create(
        user=fan,
        purpose=MFA_PURPOSE_DEVICE_RESET,
        code_hash=VALID_CODE_HASH,
        expires_at=timezone.now() + datetime.timedelta(minutes=5),
    )
    MfaChallenge.objects.create(
        user=fan,
        purpose=MFA_PURPOSE_DEVICE_RESET,
        code_hash="b" * 64,
        expires_at=timezone.now() + datetime.timedelta(minutes=5),
        consumed_at=timezone.now(),
    )
    MfaChallenge.objects.create(
        user=fan,
        purpose=MFA_PURPOSE_DEVICE_RESET,
        code_hash="c" * 64,
        expires_at=timezone.now() - datetime.timedelta(minutes=1),
    )
    MfaChallenge.objects.create(
        user=fan,
        purpose=MFA_PURPOSE_DEVICE_RESET,
        code_hash="d" * 64,
        expires_at=timezone.now() + datetime.timedelta(minutes=5),
        attempts=OTP_MAX_ATTEMPTS,
    )

    assert list(MfaChallenge.objects.for_purpose(fan, MFA_PURPOSE_DEVICE_RESET).open()) == [usable]


def test_default_auth_level_is_password_only(fan):
    """Une session fraiche ne doit JAMAIS naitre au niveau renforce."""
    session = _make_session(fan)
    assert session.auth_level == AUTH_LEVEL_PASSWORD
