"""
Token primitives — the project's cryptographic boundary.

All JWT signing and verification flows go through this module, keeping this
class of security behavior concentrated in one place.

PyJWT is used directly rather than adding another token framework because
session state and revocation already live in the `session` table. Keeping one
revocation model avoids duplicated state.

Four JWT pitfalls are addressed here and covered by tests:

1. `alg: none`: decoding receives an explicit allowed algorithm list.
2. Algorithm confusion: exactly one configured algorithm is accepted.
3. Missing expiry checks: `exp` is required and leeway is explicit.
4. Type confusion: `token_type` is required and compared strictly against the
   type expected by the caller.

`token_type` is used instead of `typ` because `typ` already names the JOSE
header field whose value is normally "JWT".
"""

from __future__ import annotations

import datetime
import uuid
from enum import StrEnum
from typing import Any

import jwt
from django.conf import settings

from apps.core.exceptions import AuthError


class TokenType(StrEnum):
    """Token type carried by the `token_type` claim and checked on decode."""

    ACCESS = "access"
    REFRESH = "refresh"


class TokenInvalidError(AuthError):
    """
    401 — unreadable, incorrectly signed, wrong-type, or incomplete token.

    A single error code intentionally covers all of these cases so callers do
    not receive extra information about how far a forged token got.
    """

    default_code = "TOKEN_INVALID"
    default_message = "Jeton invalide."


class TokenExpiredError(AuthError):
    """
    401 — expired token.

    This remains distinct from `TOKEN_INVALID` because the client needs to know
    whether it should refresh rather than force a new login.
    """

    default_code = "TOKEN_EXPIRED"
    default_message = "Jeton expire."


class TokenReuseDetectedError(AuthError):
    """
    401 — a previously rotated refresh token was replayed.

    This has a distinct code because the legitimate client must stop retrying
    and re-authenticate, while security metrics also need to count this event.
    """

    default_code = "TOKEN_REUSE_DETECTED"
    default_message = "Ce jeton a deja ete utilise. La session a ete revoquee."


def _algorithm() -> str:
    return str(settings.JWT_ALGORITHM)


def _signing_key() -> str:
    """
    Return the signing key, which must NEVER be Django's `SECRET_KEY`.

    With HS256 the same key signs and verifies tokens. Sharing it with Django
    would turn any Django secret leak into the ability to forge authentication
    tokens. Separate secrets keep the blast radii separate.
    """
    return str(settings.JWT_SIGNING_KEY)


def encode_token(
    *,
    token_type: TokenType,
    subject: uuid.UUID,
    lifetime: datetime.timedelta,
    claims: dict[str, Any] | None = None,
    issued_at: datetime.datetime,
) -> tuple[str, uuid.UUID, datetime.datetime]:
    """
    Sign a token and return `(token, jti, expiration)`.

    The `jti` and expiration are returned directly because the caller must
    persist them in `identity_session`; re-decoding a token just written would
    add needless work and another chance for divergence.

    `issued_at` is a parameter rather than an internal clock read so tests and
    paired token issuance remain deterministic.
    """
    jti = uuid.uuid4()
    expires_at = issued_at + lifetime
    payload: dict[str, Any] = {
        **(claims or {}),
        "token_type": str(token_type),
        "sub": str(subject),
        "jti": str(jti),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": str(settings.JWT_ISSUER),
    }
    token = jwt.encode(payload, _signing_key(), algorithm=_algorithm())
    return token, jti, expires_at


#: Claims required in every token. Without `exp`, `jti`, or `token_type`,
#: expiry, revocation, and type separation would not be enforceable.
REQUIRED_CLAIMS = ("exp", "iat", "jti", "sub", "token_type", "iss")


def decode_token(raw: str, *, expected_type: TokenType) -> dict[str, Any]:
    """
    Verify a token and return its claims.

    `expected_type` is mandatory and has no default so callers cannot forget
    to state whether they expect an access or refresh token.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            raw,
            _signing_key(),
            # Explicitly restrict decoding to the configured algorithm. This
            # closes both `alg: none` and algorithm-confusion paths.
            algorithms=[_algorithm()],
            issuer=str(settings.JWT_ISSUER),
            leeway=int(settings.JWT_LEEWAY_SECONDS),
            options={"require": list(REQUIRED_CLAIMS)},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.PyJWTError as exc:
        # Every other verification failure maps to the same public error code.
        raise TokenInvalidError() from exc

    if payload.get("token_type") != str(expected_type):
        raise TokenInvalidError()

    return payload
