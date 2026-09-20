"""
Adversarial tests for token primitives.

These tests forge tokens the system must reject rather than only checking a
successful round trip. They are pure functions and require no database.
"""

from __future__ import annotations

import datetime
import uuid

import jwt
import pytest

from apps.identity.tokens import (
    REQUIRED_CLAIMS,
    TokenExpiredError,
    TokenInvalidError,
    TokenType,
    decode_token,
    encode_token,
)

SUBJECT = uuid.UUID("11111111-1111-4111-8111-111111111111")
ACCESS_LIFETIME = datetime.timedelta(minutes=15)
REFRESH_LIFETIME = datetime.timedelta(days=7)


def now() -> datetime.datetime:
    """Use the current instant with explicit offsets rather than a fixed issue date that eventually makes every token expired."""
    return datetime.datetime.now(datetime.timezone.utc)


def issue(token_type: TokenType = TokenType.ACCESS, *, at=None, lifetime=ACCESS_LIFETIME, **claims):
    return encode_token(
        token_type=token_type,
        subject=SUBJECT,
        lifetime=lifetime,
        claims=claims,
        issued_at=at or now(),
    )


# ===========================================================================
# Aller-retour nominal
# ===========================================================================


def test_an_access_token_round_trips_with_its_business_claims(settings):
    token, jti, expires_at = issue(role="FAN", did="d-1", sid="s-1", auth_level=1)

    claims = decode_token(token, expected_type=TokenType.ACCESS)

    assert claims["sub"] == str(SUBJECT)
    assert claims["role"] == "FAN"
    assert claims["auth_level"] == 1
    assert claims["jti"] == str(jti)
    assert claims["exp"] == int(expires_at.timestamp())


def test_the_identifier_and_expiry_are_returned_rather_than_re_read(settings):
    """Return jti and expiration directly so callers can persist exactly what was signed without re-decoding the token."""
    moment = now()
    token, jti, expires_at = issue(at=moment, lifetime=REFRESH_LIFETIME)

    assert expires_at == moment + REFRESH_LIFETIME
    assert decode_token(token, expected_type=TokenType.ACCESS)["jti"] == str(jti)


def test_two_tokens_issued_in_the_same_instant_have_different_identifiers(settings):
    """Each concurrently issued session must receive a distinct jti."""
    moment = now()
    _, first, _ = issue(at=moment)
    _, second, _ = issue(at=moment)

    assert first != second


# ===========================================================================
# Piege n° 4 : confusion de type
# ===========================================================================


def test_a_refresh_token_is_refused_where_an_access_token_is_expected(settings):
    """A refresh token must never be accepted as an access token, or long-lived tokens would bypass rotation entirely."""
    refresh, _, _ = issue(TokenType.REFRESH, lifetime=REFRESH_LIFETIME, family=str(uuid.uuid4()))

    with pytest.raises(TokenInvalidError):
        decode_token(refresh, expected_type=TokenType.ACCESS)


def test_an_access_token_is_refused_where_a_refresh_token_is_expected(settings):
    """The inverse type confusion must be rejected as well."""
    access, _, _ = issue(TokenType.ACCESS)

    with pytest.raises(TokenInvalidError):
        decode_token(access, expected_type=TokenType.REFRESH)


# ===========================================================================
# Piege n° 1 : alg none
# ===========================================================================


def test_a_token_declaring_no_signature_is_refused(settings):
    """Reject alg:none by restricting decoding to the configured expected algorithm."""
    forged = jwt.encode(
        {
            "sub": str(SUBJECT),
            "token_type": "access",
            "role": "ADMIN",
            "jti": str(uuid.uuid4()),
            "iat": int(now().timestamp()),
            "exp": int((now() + ACCESS_LIFETIME).timestamp()),
            "iss": settings.JWT_ISSUER,
        },
        "",
        algorithm="none",
    )

    with pytest.raises(TokenInvalidError):
        decode_token(forged, expected_type=TokenType.ACCESS)


# ===========================================================================
# Piege n° 2 : confusion d algorithme
# ===========================================================================


def test_a_token_signed_with_another_algorithm_is_refused(settings):
    """Reject a token signed with the same key under a different algorithm, preventing algorithm confusion."""
    forged = jwt.encode(
        {
            "sub": str(SUBJECT),
            "token_type": "access",
            "jti": str(uuid.uuid4()),
            "iat": int(now().timestamp()),
            "exp": int((now() + ACCESS_LIFETIME).timestamp()),
            "iss": settings.JWT_ISSUER,
        },
        # Use a longer key only to avoid PyJWT's SHA-512 key-length warning; the test targets algorithm rejection.
        # qu il annonce.
        (settings.JWT_SIGNING_KEY * 4)[:64],
        algorithm="HS512",
    )

    with pytest.raises(TokenInvalidError):
        decode_token(forged, expected_type=TokenType.ACCESS)


def test_a_token_signed_with_the_django_secret_key_is_refused(settings):
    """JWT signing key and Django SECRET_KEY must remain separate secrets with separate blast radii."""
    forged = jwt.encode(
        {
            "sub": str(SUBJECT),
            "token_type": "access",
            "role": "ADMIN",
            "jti": str(uuid.uuid4()),
            "iat": int(now().timestamp()),
            "exp": int((now() + ACCESS_LIFETIME).timestamp()),
            "iss": settings.JWT_ISSUER,
        },
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    assert settings.JWT_SIGNING_KEY != settings.SECRET_KEY
    with pytest.raises(TokenInvalidError):
        decode_token(forged, expected_type=TokenType.ACCESS)


def test_a_tampered_payload_breaks_the_signature(settings):
    """Changing the role claim without a valid signature must be rejected."""
    token, _, _ = issue(role="FAN")
    header, payload, signature = token.split(".")
    escalated = jwt.encode({"role": "ADMIN"}, "", algorithm="none").split(".")[1]

    with pytest.raises(TokenInvalidError):
        decode_token(f"{header}.{escalated}.{signature}", expected_type=TokenType.ACCESS)


# ===========================================================================
# Piege n° 3 : expiration
# ===========================================================================


def test_an_expired_token_is_reported_as_expired_not_as_invalid(settings):
    """Expired tokens keep a distinct public error so clients know to refresh instead of forcing a new login."""
    settings.JWT_LEEWAY_SECONDS = 0
    long_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
    token, _, _ = issue(at=long_ago)

    with pytest.raises(TokenExpiredError):
        decode_token(token, expected_type=TokenType.ACCESS)


def test_the_clock_tolerance_is_bounded_and_explicit(settings):
    """Clock-skew leeway comes from bounded settings rather than an arbitrary generous tolerance."""
    settings.JWT_LEEWAY_SECONDS = 60
    just_expired = (
        datetime.datetime.now(datetime.timezone.utc) - ACCESS_LIFETIME - datetime.timedelta(seconds=5)
    )
    token, _, _ = issue(at=just_expired)

    assert decode_token(token, expected_type=TokenType.ACCESS)["sub"] == str(SUBJECT)

    settings.JWT_LEEWAY_SECONDS = 0
    with pytest.raises(TokenExpiredError):
        decode_token(token, expected_type=TokenType.ACCESS)


# ===========================================================================
# Claims obligatoires et emetteur
# ===========================================================================


@pytest.mark.parametrize("missing", REQUIRED_CLAIMS)
def test_a_token_missing_any_required_claim_is_refused(settings, missing):
    """Require exp, jti, and token_type explicitly so tokens cannot become immortal, irrevocable, or interchangeable."""
    payload = {
        "sub": str(SUBJECT),
        "token_type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(now().timestamp()),
        "exp": int((datetime.datetime.now(datetime.timezone.utc) + ACCESS_LIFETIME).timestamp()),
        "iss": settings.JWT_ISSUER,
    }
    del payload[missing]
    forged = jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises((TokenInvalidError, TokenExpiredError)):
        decode_token(forged, expected_type=TokenType.ACCESS)


def test_a_token_from_another_issuer_is_refused(settings):
    """Verify issuer now so a future additional issuer cannot become trusted implicitly."""
    forged = jwt.encode(
        {
            "sub": str(SUBJECT),
            "token_type": "access",
            "jti": str(uuid.uuid4()),
            "iat": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
            "exp": int((datetime.datetime.now(datetime.timezone.utc) + ACCESS_LIFETIME).timestamp()),
            "iss": "un-autre-service",
        },
        settings.JWT_SIGNING_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(TokenInvalidError):
        decode_token(forged, expected_type=TokenType.ACCESS)


def test_garbage_is_refused_without_raising_anything_else(settings):
    """Malformed non-token input must never surface as a server error."""
    for rubbish in ("", "abc", "a.b.c", "Bearer x.y.z", "." * 40):
        with pytest.raises(TokenInvalidError):
            decode_token(rubbish, expected_type=TokenType.ACCESS)


def test_no_secret_ever_reaches_the_payload(settings):
    """JWT payloads are signed, not encrypted; keep the emitted claim set intentionally minimal and auditable."""
    token, _, _ = issue(role="FAN", did="d-1", sid="s-1", auth_level=1)
    claims = decode_token(token, expected_type=TokenType.ACCESS)

    assert set(claims) == {
        "sub",
        "role",
        "did",
        "sid",
        "auth_level",
        "token_type",
        "jti",
        "iat",
        "exp",
        "iss",
    }
    assert settings.JWT_SIGNING_KEY not in token.split(".")[1]
