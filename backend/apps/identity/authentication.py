"""
DRF authentication class for `Authorization: Bearer <access>`.

This is where a signed token becomes an authenticated user. Verification happens
in three stages: token signature/type, persistent session state, then bound
device state.

The session is re-read on every authenticated request so logout, password
changes, and refresh-reuse revocation take effect immediately rather than only
when the access token expires. The same query loads user, role, and device.

The server authorizes from current database-backed user/session state, not from
the token's role claim. Device verification also lives here so JWT verification
remains in a single cryptographic boundary instead of being duplicated in
middleware.
"""

from __future__ import annotations

import functools
import logging
import uuid
from typing import Any, cast

from rest_framework.authentication import BaseAuthentication, get_authorization_header

from .locks import build_device_lock
from .models import Session
from .services.devices import DeviceBindingService
from .tokens import TokenInvalidError, TokenType, decode_token

logger = logging.getLogger("fanid.identity")

AUTH_SCHEME = b"bearer"

JWT_PREAUTH_RESULT_ATTR = "_fanid_jwt_preauth_result"
JWT_PREAUTH_ERROR_ATTR = "_fanid_jwt_preauth_error"
_PREAUTH_MISSING = object()


@functools.lru_cache(maxsize=1)
def default_binding_service() -> DeviceBindingService:
    """Process-shared binding service; cache it so requests reuse the lazy Redis client."""
    return DeviceBindingService(lock=build_device_lock())


class JWTAuthentication(BaseAuthentication):
    """Resout l utilisateur a partir d un jeton d acces."""

    def __init__(self, binding_service: DeviceBindingService | None = None) -> None:
        # DRF instantiates authentication classes without arguments. The optional
        # parameter exists only so tests can inject a lock backend.
        # memoire plutot que Redis.
        self._binding = binding_service

    @property
    def binding(self) -> DeviceBindingService:
        return self._binding or default_binding_service()

    def authenticate_header(self, request: Any) -> str:
        """Returned with 401 to identify the expected authentication scheme."""
        return 'Bearer realm="api"'

    def authenticate(self, request: Any) -> tuple[Any, dict[str, Any]] | None:
        raw_request = getattr(request, "_request", request)

        cached_error = getattr(
            raw_request,
            JWT_PREAUTH_ERROR_ATTR,
            None,
        )
        if cached_error is not None:
            raise cached_error

        cached_result = getattr(
            raw_request,
            JWT_PREAUTH_RESULT_ATTR,
            _PREAUTH_MISSING,
        )
        if cached_result is not _PREAUTH_MISSING:
            if cached_result is not None:
                for attribute in ("auth_level", "session_id"):
                    if hasattr(raw_request, attribute):
                        setattr(
                            request,
                            attribute,
                            getattr(raw_request, attribute),
                        )
            return cast(
                tuple[Any, dict[str, Any]] | None,
                cached_result,
            )

        raw = self._extract_token(request)
        if raw is None:
            # No Bearer header is not an authentication error; DRF may try other
            # authenticators or continue as anonymous.
            # publics — l inscription en premier.
            return None

        claims = decode_token(raw, expected_type=TokenType.ACCESS)
        session = self._load_session(claims)
        user = session.user

        if not user.is_active or user.anonymized_at is not None:
            # Disabled or anonymized accounts may still hold cryptographically valid tokens;
            # reject them here without exposing a distinct account-state oracle.
            raise TokenInvalidError()

        self.binding.assert_matches(user=user, device_id=claims.get("did"))

        # Read authentication level from the session rather than a stale token claim so
        # step-up changes take effect immediately.
        # RETROGRADATION soit ignoree.
        request.auth_level = session.auth_level
        request.session_id = session.pk

        return (user, claims)

    # -- details ------------------------------------------------------------

    @staticmethod
    def _extract_token(request: Any) -> str | None:
        header = get_authorization_header(request).split()
        if not header or header[0].lower() != AUTH_SCHEME:
            return None
        if len(header) != 2:
            # A malformed Bearer header clearly attempted token authentication, so reject it
            # instead of silently falling through.
            # de retomber en anonyme, sinon l appelant recevrait un 403
            # incomprehensible au lieu d un 401 explicite.
            raise TokenInvalidError()
        try:
            return header[1].decode()
        except UnicodeDecodeError as exc:
            raise TokenInvalidError() from exc

    def _load_session(self, claims: dict[str, Any]) -> Session:
        """Load the active session named by `sid`, requiring both unrevoked and unexpired state."""
        try:
            # Convert the session identifier before querying so malformed UUID claims become
            # authentication failures rather than model-field errors.
            session_id = uuid.UUID(str(claims.get("sid")))
        except (TypeError, ValueError) as exc:
            raise TokenInvalidError() from exc

        session = (
            Session.objects.active()
            .select_related("user", "user__role", "device")
            .filter(pk=session_id)
            .first()
        )
        if session is None:
            # Session revoquee, expiree, ou identifiant inconnu : meme reponse.
            # Distinguer « revoquee » de « inconnue » apprendrait a un attaquant
            # que son jeton a ete repere.
            logger.info("auth.token.session_not_active")
            raise TokenInvalidError()
        return session
