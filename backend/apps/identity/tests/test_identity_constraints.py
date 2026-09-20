"""
Identity-model invariants proven directly at the database layer.

These tests use direct SQL writes so they verify database constraints rather
than merely re-testing ORM or service validation.
"""

import datetime
import uuid

import pytest
from django.db import IntegrityError, connection, transaction

from apps.identity.constants import DEFAULT_ROLE, ROLE_IDS, ROLE_NAMES
from apps.identity.models import Role, User

# Apply the role fixture to the whole module because every constraint test
# depends on the reference rows.
pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("roles")]


def _insert_user_sql(email, date_of_birth, created_at="2025-01-01T00:00:00+00", role_name=DEFAULT_ROLE):
    """Insert directly with SQL, bypassing ORM and services completely."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO identity_user
                (id, password, is_superuser, first_name, last_name, is_staff, is_active,
                 date_joined, email, date_of_birth, terms_accepted_at, created_at,
                 updated_at, version, role_id)
            VALUES (%s, '!', false, '', '', false, true, now(), %s, %s, now(), %s, now(), 1, %s)
            """,
            [uuid.uuid4(), email, date_of_birth, created_at, ROLE_IDS[role_name]],
        )


# --------------------------------------------------------------- reference data


def test_the_four_roles_are_seeded_with_stable_identifiers():
    """Role identifiers are fixed so fixtures remain portable across environments."""
    assert Role.objects.count() == 4
    for name in ROLE_NAMES:
        assert Role.objects.get(name=name).id == ROLE_IDS[name]


def test_database_rejects_an_unknown_role_name():
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO identity_role (id, name, permissions, created_at) "
                "VALUES (%s, 'SUPERVISOR', '{}', now())",
                [uuid.uuid4()],
            )


def test_a_role_still_referenced_cannot_be_deleted():
    """`PROTECT` prevents deleting a role from deleting its users."""
    User.objects.create_user(
        email="protect@example.test",
        password="irrelevant-here-x9",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
    )
    from django.db.models import ProtectedError

    with pytest.raises(ProtectedError):
        Role.objects.get(name=DEFAULT_ROLE).delete()


# ------------------------------------------------------------------- age


def test_database_rejects_a_user_under_sixteen_at_signup():
    """The database rejects underage rows even when services are bypassed."""
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_user_sql("kid@example.test", "2015-01-01", created_at="2025-01-01T00:00:00+00")


def test_database_accepts_a_user_exactly_sixteen_at_signup():
    """The minimum-age boundary is inclusive."""
    _insert_user_sql("just16@example.test", "2009-01-01", created_at="2025-01-01T00:00:00+00")
    assert User.objects.filter(email="just16@example.test").exists()


def test_database_rejects_a_user_one_day_short_of_sixteen():
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_user_sql("almost16@example.test", "2009-01-02", created_at="2025-01-01T00:00:00+00")


def test_the_age_rule_is_evaluated_at_signup_not_today():
    """The age constraint is anchored to account creation time, making historical validation deterministic."""
    _insert_user_sql("old@example.test", "1980-06-15", created_at="2016-06-14T00:00:00+00")
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_user_sql("backdated@example.test", "2001-06-15", created_at="2016-06-14T00:00:00+00")


# ------------------------------------------------------------------ email


def test_email_uniqueness_ignores_case():
    User.objects.create_user(
        email="Fan@Example.TEST",
        password="irrelevant-here-x9",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        _insert_user_sql("fan@example.test", "1990-01-01")


def test_email_lookup_ignores_case_without_lower():
    """`citext` provides case-insensitive behavior without caller-side `LOWER()` calls."""
    User.objects.create_user(
        email="Mixed@Example.TEST",
        password="irrelevant-here-x9",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
    )
    # `normalize_email()` lowercases the domain only. Storage normalization and
    # database case-insensitive uniqueness are separate behaviors.
    assert User.objects.get_by_email_ci("MIXED@EXAMPLE.TEST").email == "Mixed@example.test"
    assert User.objects.filter(email="mixed@example.test").exists()
    assert User.objects.filter(email="MIXED@EXAMPLE.TEST").exists()


# --------------------------------------------------------------- username


def test_username_is_no_longer_unique_nor_required():
    """`username` is neutralized rather than removed; multiple email-identified users may keep it null."""
    for email in ("u1@example.test", "u2@example.test"):
        User.objects.create_user(
            email=email,
            password="irrelevant-here-x9",
            date_of_birth=datetime.date(1990, 1, 1),
            terms_accepted_at=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        )
    assert User.objects.filter(username__isnull=True).count() == 2


def test_email_is_the_authentication_identifier():
    assert User.USERNAME_FIELD == "email"
    assert "date_of_birth" in User.REQUIRED_FIELDS


# ---------------------------------------------------------------- manager


def test_manager_refuses_to_build_an_incomplete_user():
    """No code path may create a normal user without recorded terms acceptance."""
    with pytest.raises(ValueError):
        User.objects.create_user(
            email="no-terms@example.test",
            password="irrelevant-here-x9",
            date_of_birth=datetime.date(1990, 1, 1),
            terms_accepted_at=None,
        )
    with pytest.raises(ValueError):
        User.objects.create_user(
            email="no-dob@example.test",
            password="irrelevant-here-x9",
            date_of_birth=None,
            terms_accepted_at=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        )


def test_public_registration_default_role_is_the_least_privileged():
    """Public user creation must never permit arbitrary privilege assignment."""
    user = User.objects.create_user(
        email="default-role@example.test",
        password="irrelevant-here-x9",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
    )
    assert user.role.name == DEFAULT_ROLE
    assert user.is_staff is False
    assert user.is_superuser is False
