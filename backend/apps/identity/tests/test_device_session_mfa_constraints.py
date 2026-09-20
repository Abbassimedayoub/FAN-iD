"""
Database-level invariants for `Device`, `Session`, and `MfaChallenge`.

Constraints are exercised with direct SQL so these tests prove database
enforcement independently from ORM or service validation.
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
    """Partial uniqueness allows one active device while retaining revoked history."""
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
    """The reset flow depends on this behavior."""
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
    """The varchar type, rather than the CHECK constraint, enforces the maximum stored length."""
    with pytest.raises(DataError), transaction.atomic():
        _insert_device_sql(fan, fingerprint="a" * 65)


def test_database_rejects_an_unknown_platform(fan):
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_device_sql(fan, platform="symbian")


def test_a_revoked_device_must_carry_a_reason(fan):
    """A revocation without a reason has incomplete audit value."""
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_device_sql(fan, revoked_at=timezone.now(), revoked_reason=None)


def test_a_revocation_reason_requires_a_revocation_date(fan):
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_device_sql(fan, revoked_at=None, revoked_reason=DEVICE_REVOKED_USER_RESET)


def test_deleting_a_user_removes_their_devices(fan):
    """Device fingerprints are personal data and should not outlive the account unnecessarily."""
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
    """Two sessions cannot claim the same current refresh token identifier."""
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
    """Active sessions must be both unrevoked and unexpired."""
    valid = _make_session(fan)
    _make_session(fan, revoked_at=timezone.now(), revoked_reason="LOGOUT")
    # Create an expired session by backdating issuance; the database correctly
    # rejects a session whose expiration precedes its issuance.
    _make_session(
        fan,
        issued_at=timezone.now() - datetime.timedelta(days=8),
        expires_at=timezone.now() - datetime.timedelta(days=1),
    )

    assert list(Session.objects.for_user(fan).active()) == [valid]


def test_a_whole_family_can_be_revoked_at_once(fan):
    """The family is the revocation unit after refresh-token reuse."""
    family = uuid.uuid4()
    for _ in range(3):
        _make_session(fan, family_id=family)
    other = _make_session(fan)

    Session.objects.for_family(family).update(revoked_at=timezone.now(), revoked_reason="ROTATION_REUSE")
    assert Session.objects.for_family(family).active().count() == 0
    assert Session.objects.filter(pk=other.pk).active().count() == 1


def test_a_session_survives_the_purge_of_its_device(fan):
    """`SET_NULL` preserves session audit history when device rows are removed."""
    _insert_device_sql(fan)
    device = Device.objects.for_user(fan).active().get()
    session = _make_session(fan, device=device)
    device.delete()
    session.refresh_from_db()
    assert session.device_id is None


# ====================================================== MfaChallenge


def test_database_refuses_to_store_a_plaintext_code(fan):
    """The database requires `code_hash` to contain a SHA-256 digest rather than a plaintext code."""
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
    """`open()` is the canonical definition of a still-usable challenge."""
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
    """A newly created session must never start at the step-up authentication level."""
    session = _make_session(fan)
    assert session.auth_level == AUTH_LEVEL_PASSWORD
