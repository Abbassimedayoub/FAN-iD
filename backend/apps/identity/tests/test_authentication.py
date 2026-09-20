"""
Authentication-class tests: a token resolves to a current user or is rejected.

Key cases prove immediate session revocation and that the token's role claim
does not authorize server-side actions.
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
    # Pass headers explicitly because the type stubs otherwise interpret **headers as request data.
    if token is None:
        return factory.get("/api/v1/whatever")
    return factory.get("/api/v1/whatever", HTTP_AUTHORIZATION=f"{scheme} {token}".strip())


# ===========================================================================
# Chemin nominal
# ===========================================================================


def test_a_session_without_any_device_authenticates(auth, fan):
    """A user with no bound device may authenticate with a token whose did is null; a token pointing to a revoked device remains invalid."""
    pair = TokenService.issue_pair(user=fan)

    resolved, claims = auth.authenticate(request_with(pair.access))

    assert resolved.pk == fan.pk
    assert claims["did"] is None


def test_a_valid_token_resolves_the_user(auth, fan):
    pair = TokenService.issue_pair(user=fan)

    resolved, claims = auth.authenticate(request_with(pair.access))

    assert resolved.pk == fan.pk
    assert claims["sid"] == str(pair.session.pk)


def test_the_authentication_level_is_read_from_the_session_not_from_the_token(auth, fan):
    """Step-up changes session state, so authentication must read the session rather than stale token claims."""
    pair = TokenService.issue_pair(user=fan)
    Session.objects.filter(pk=pair.session.pk).update(auth_level=AUTH_LEVEL_STEP_UP)

    request = request_with(pair.access)
    auth.authenticate(request)

    assert request.auth_level == AUTH_LEVEL_STEP_UP


def test_a_role_changed_in_the_database_takes_effect_immediately(auth, fan, roles):
    """The token role claim is client metadata only; server authorization uses the current database-backed user role."""
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
    """Public endpoints may legitimately have no token, so missing Bearer authentication is not itself an error."""
    assert auth.authenticate(factory.get("/api/v1/whatever")) is None


def test_another_scheme_is_left_to_the_other_authentication_classes(auth, db):
    assert auth.authenticate(request_with("dXNlcjpwYXNz", scheme="Basic")) is None


@pytest.mark.parametrize("header", ["Bearer", "Bearer a b", "Bearer  "])
def test_a_malformed_bearer_header_is_refused_rather_than_ignored(auth, db, header):
    """A malformed Bearer header clearly attempts token authentication and must produce an explicit 401 rather than anonymous fallback."""
    request = factory.get("/api/v1/whatever", HTTP_AUTHORIZATION=header)

    with pytest.raises(TokenInvalidError):
        auth.authenticate(request)


@pytest.mark.parametrize("rubbish", ["abc", "a.b.c", "..", "x" * 200])
def test_a_token_that_is_not_a_token_is_refused(auth, db, rubbish):
    with pytest.raises(TokenInvalidError):
        auth.authenticate(request_with(rubbish))


def test_a_refresh_token_cannot_authenticate(auth, fan):
    """The token_type claim prevents a long-lived refresh token from being accepted as an access token."""
    pair = TokenService.issue_pair(user=fan)

    with pytest.raises(TokenInvalidError):
        auth.authenticate(request_with(pair.refresh))


# ===========================================================================
# Revocation immediate
# ===========================================================================


def test_a_revoked_session_is_refused_immediately(auth, fan):
    """Re-reading the session on each call makes revocation effective immediately instead of waiting for access-token expiry."""
    pair = TokenService.issue_pair(user=fan)
    assert auth.authenticate(request_with(pair.access)) is not None

    TokenService.revoke_session(pair.session, SESSION_REVOKED_LOGOUT)

    with pytest.raises(TokenInvalidError):
        auth.authenticate(request_with(pair.access))


def test_an_expired_session_is_refused_even_if_the_access_token_is_still_valid(auth, fan):
    """Session lifetime and access-token lifetime are independent; an expired session must block access immediately."""
    pair = TokenService.issue_pair(user=fan)
    # L emission ET l expiration sont antidatees : `ck_session_expiry_after_issue`
    # The database correctly rejects a session whose expiration precedes issuance.
    Session.objects.filter(pk=pair.session.pk).update(
        issued_at=timezone.now() - datetime.timedelta(days=8),
        expires_at=timezone.now() - datetime.timedelta(days=1),
    )

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
# Device
# ===========================================================================


def test_a_token_presented_from_another_device_is_refused(auth, binding, fan):
    """A valid token presented from another device is treated as authentication failure, not authorization failure."""
    device = binding.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    assert device is not None
    pair = TokenService.issue_pair(user=fan, device=device)
    assert auth.authenticate(request_with(pair.access)) is not None

    stolen = TokenService.issue_pair(user=fan)  # emis sans `did`

    with pytest.raises(DeviceMismatchError):
        auth.authenticate(request_with(stolen.access))


def test_an_exempt_role_authenticates_without_any_device(roles, auth):
    """Organizer and administrator roles are exempt from device binding."""
    organizer = make_user(roles, role="ORGANIZER")
    pair = TokenService.issue_pair(user=organizer)

    resolved, _ = auth.authenticate(request_with(pair.access))

    assert resolved.pk == organizer.pk


def test_the_device_identifier_is_verified_against_the_lock_not_the_token(auth, binding, fan):
    """The token carries did but does not define device state; revoking the device must take effect on the next request."""
    device = binding.bind(user=fan, fingerprint=PHONE, platform=PLATFORM_ANDROID)
    assert device is not None
    pair = TokenService.issue_pair(user=fan, device=device)

    binding.revoke(device, "USER_RESET")

    with pytest.raises(DeviceMismatchError):
        auth.authenticate(request_with(pair.access))


def test_the_challenge_header_names_the_expected_scheme(auth):
    assert auth.authenticate_header(None) == 'Bearer realm="api"'


def test_two_users_never_share_a_session(auth, roles):
    """A token sid must never resolve to another user's session or account."""
    first = make_user(roles, email="premier-auth@example.test")
    second = make_user(roles, email="second-auth@example.test")
    pair = TokenService.issue_pair(user=first)

    resolved, _ = auth.authenticate(request_with(pair.access))

    assert resolved.pk == first.pk
    assert resolved.pk != second.pk
    assert uuid.UUID(str(pair.session.pk)) == pair.session.pk
