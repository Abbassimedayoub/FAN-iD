"""
Token lifecycle tests cover issuance, rotation, reuse detection, and revocation.

The concurrency test uses two real threads against the database to prove that
only one rotation can win, exercising the invariant that exists only under
concurrent access.
"""

from __future__ import annotations

import datetime
import threading
import uuid

import pytest
from django.db import connection
from django.utils import timezone

from apps.identity.constants import (
    SESSION_REVOKED_LOGOUT,
    SESSION_REVOKED_PASSWORD_CHANGE,
    SESSION_REVOKED_ROTATION_REUSE,
)
from apps.identity.models import Session, User
from apps.identity.services.tokens import TokenService
from apps.identity.tokens import (
    TokenExpiredError,
    TokenInvalidError,
    TokenReuseDetectedError,
    TokenType,
    decode_token,
)


def make_user(roles, email="rotation@example.test") -> User:
    return User.objects.create_user(
        email=email,
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1996, 5, 4),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


@pytest.fixture
def fan(db, roles) -> User:
    return make_user(roles)


# ===========================================================================
# Issuance
# ===========================================================================


def test_issuing_a_pair_opens_a_session_row_aligned_with_the_tokens(fan):
    """The refresh `jti` and session identifier must exactly match persisted session state."""
    pair = TokenService.issue_pair(user=fan)

    session = Session.objects.get(pk=pair.session.pk)
    refresh_claims = decode_token(pair.refresh, expected_type=TokenType.REFRESH)
    access_claims = decode_token(pair.access, expected_type=TokenType.ACCESS)

    assert str(session.refresh_jti) == refresh_claims["jti"]
    assert access_claims["sid"] == str(session.pk)
    assert refresh_claims["family"] == str(session.family_id)
    assert session.expires_at == pair.refresh_expires_at
    assert session.revoked_at is None


def test_the_access_token_carries_the_role_so_authorization_costs_no_query(fan):
    """The access token carries the role so authorization can read it without an extra query."""
    pair = TokenService.issue_pair(user=fan)

    claims = decode_token(pair.access, expected_type=TokenType.ACCESS)

    assert claims["role"] == "FAN"
    assert claims["auth_level"] == 1
    # With no bound device, the claim is explicitly null rather than omitted.
    assert claims["did"] is None


def test_the_refresh_token_never_carries_the_role_or_the_device(fan):
    """A refresh token exists only to obtain access tokens and must not carry access privileges."""
    claims = decode_token(TokenService.issue_pair(user=fan).refresh, expected_type=TokenType.REFRESH)

    assert set(claims) == {"family", "token_type", "sub", "jti", "iat", "exp", "iss"}


def test_two_logins_open_two_independent_families(fan):
    first = TokenService.issue_pair(user=fan)
    second = TokenService.issue_pair(user=fan)

    assert first.session.family_id != second.session.family_id
    assert Session.objects.filter(user=fan, revoked_at__isnull=True).count() == 2


# ===========================================================================
# Rotation
# ===========================================================================


def test_rotating_keeps_the_session_and_the_family_but_changes_the_token(fan):
    """Rotation advances the existing session lineage rather than creating a new session row."""
    original = TokenService.issue_pair(user=fan)

    rotated = TokenService.rotate(original.refresh)

    assert rotated.session.pk == original.session.pk
    assert rotated.session.family_id == original.session.family_id
    assert rotated.refresh != original.refresh

    session = Session.objects.get(pk=original.session.pk)
    assert str(session.refresh_jti) == decode_token(rotated.refresh, expected_type=TokenType.REFRESH)["jti"]
    assert Session.objects.filter(user=fan).count() == 1


def test_an_access_token_cannot_be_rotated(fan):
    pair = TokenService.issue_pair(user=fan)

    with pytest.raises(TokenInvalidError):
        TokenService.rotate(pair.access)


def test_an_expired_refresh_is_reported_as_expired(fan, settings):
    settings.JWT_LEEWAY_SECONDS = 0
    long_ago = timezone.now() - datetime.timedelta(days=8)
    pair = TokenService.issue_pair(user=fan, now=long_ago)

    with pytest.raises(TokenExpiredError):
        TokenService.rotate(pair.refresh)


def test_a_refresh_from_a_revoked_session_is_invalid_not_a_reuse(fan):
    """Replaying a refresh after explicit logout is invalid, but is not classified as reuse detection."""
    pair = TokenService.issue_pair(user=fan)
    TokenService.revoke_session(pair.session, SESSION_REVOKED_LOGOUT)

    with pytest.raises(TokenInvalidError) as caught:
        TokenService.rotate(pair.refresh)
    assert not isinstance(caught.value, TokenReuseDetectedError)


# ===========================================================================
# Reuse detection
# ===========================================================================


def test_replaying_a_rotated_refresh_revokes_the_whole_family(fan):
    """A replayed rotated refresh revokes the whole family because the server cannot identify the legitimate holder."""
    original = TokenService.issue_pair(user=fan)
    rotated = TokenService.rotate(original.refresh)

    with pytest.raises(TokenReuseDetectedError):
        TokenService.rotate(original.refresh)

    session = Session.objects.get(pk=original.session.pk)
    assert session.revoked_at is not None
    assert session.revoked_reason == SESSION_REVOKED_ROTATION_REUSE

    # The newly issued legitimate refresh is revoked with the compromised family.
    with pytest.raises(TokenInvalidError):
        TokenService.rotate(rotated.refresh)


def test_a_reuse_in_one_family_leaves_the_other_sessions_alive(fan):
    """Reuse revocation is scoped to one family so unrelated sessions remain active."""
    compromised = TokenService.issue_pair(user=fan)
    untouched = TokenService.issue_pair(user=fan)
    TokenService.rotate(compromised.refresh)

    with pytest.raises(TokenReuseDetectedError):
        TokenService.rotate(compromised.refresh)

    assert Session.objects.get(pk=untouched.session.pk).revoked_at is None
    assert TokenService.rotate(untouched.refresh) is not None


def test_a_forged_family_claim_does_not_revoke_anything(fan):
    """The family claim confirms reuse but never locates the session; current-session lookup is keyed by unique `jti`."""
    alive = TokenService.issue_pair(user=fan)
    orphan = TokenService.issue_pair(user=fan)
    Session.objects.filter(pk=orphan.session.pk).delete()

    with pytest.raises(TokenInvalidError):
        TokenService.rotate(orphan.refresh)

    assert Session.objects.get(pk=alive.session.pk).revoked_at is None


# ===========================================================================
# Revocation
# ===========================================================================


def test_changing_a_password_must_be_able_to_close_every_session(fan):
    """Password changes must be able to revoke every session authenticated with the previous credential."""
    first = TokenService.issue_pair(user=fan)
    second = TokenService.issue_pair(user=fan)

    closed = TokenService.revoke_all_for_user(fan, SESSION_REVOKED_PASSWORD_CHANGE)

    assert closed == 2
    for pair in (first, second):
        assert Session.objects.get(pk=pair.session.pk).revoked_reason == SESSION_REVOKED_PASSWORD_CHANGE
        with pytest.raises(TokenInvalidError):
            TokenService.rotate(pair.refresh)


def test_revoking_twice_reports_no_second_victim(fan):
    """Revocation is idempotent and must not overwrite the original audit reason on a second call."""
    pair = TokenService.issue_pair(user=fan)
    TokenService.revoke_family(pair.session.family_id, SESSION_REVOKED_ROTATION_REUSE)

    assert TokenService.revoke_family(pair.session.family_id, SESSION_REVOKED_LOGOUT) == 0
    assert Session.objects.get(pk=pair.session.pk).revoked_reason == SESSION_REVOKED_ROTATION_REUSE


# ===========================================================================
# Real concurrency
# ===========================================================================


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_rotations_never_produce_two_valid_pairs(roles):
    """
    Two threads, one real database, one winner.

    Without `SELECT ... FOR UPDATE`, both transactions could replace the same
    current refresh state. The losing rotation is classified as reuse and the
    family is revoked.
    """
    fan = make_user(roles, email="concurrence@example.test")
    pair = TokenService.issue_pair(user=fan)

    start = threading.Barrier(2)
    winners: list[object] = []
    losers: list[Exception] = []

    def rotate_once() -> None:
        start.wait(timeout=5)
        try:
            winners.append(TokenService.rotate(pair.refresh))
        except Exception as exc:  # capture so the losing exception type can be asserted
            losers.append(exc)
        finally:
            # Each thread opens its own database connection and closes it before teardown.
            connection.close()

    threads = [threading.Thread(target=rotate_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
        assert not thread.is_alive(), "rotation bloquee : verrou non libere"

    # Include both winner and loser lists in the assertion diagnostic so failures
    # accurately describe concurrent outcomes.
    diagnostic = f"gagnants={winners!r} perdants={losers!r}"
    assert len(winners) == 1, diagnostic
    assert len(losers) == 1, diagnostic
    assert isinstance(losers[0], TokenReuseDetectedError), diagnostic

    session = Session.objects.get(pk=pair.session.pk)
    assert session.revoked_reason == SESSION_REVOKED_ROTATION_REUSE


@pytest.mark.django_db(transaction=True)
def test_a_family_identifier_is_never_reused_across_users(roles):
    """Two accounts must never share a token family, or revocation would cross account boundaries."""
    first = make_user(roles, email="famille-1@example.test")
    second = make_user(roles, email="famille-2@example.test")

    families = {
        TokenService.issue_pair(user=first).session.family_id,
        TokenService.issue_pair(user=second).session.family_id,
    }

    assert len(families) == 2
    assert all(isinstance(family, uuid.UUID) for family in families)
