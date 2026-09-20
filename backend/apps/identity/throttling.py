"""
Custom rate limits for the identity context.

Some limits need keys unavailable to standard DRF throttles, such as the target
account before authentication or the session identifier carried by a refresh
token.
"""

from __future__ import annotations

import hashlib
from typing import Any

from django.conf import settings
from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle

from .constants import CLIENT_WEB
from .tokens import TokenInvalidError, TokenType, decode_token


class AtomicFixedWindowRateThrottle(SimpleRateThrottle):
    """Apply a fixed-window counter using an atomic cache increment."""

    def allow_request(self, request: Any, view: Any) -> bool:
        if self.rate is None:
            return True

        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True

        now = self.timer()
        window = int(now // self.duration)
        bucket_key = f"{self.key}:{window}"
        remaining = self.duration - (now % self.duration)
        timeout = max(1, int(remaining) + 1)

        if cache.add(bucket_key, 1, timeout=timeout):
            count = 1
        else:
            try:
                count = cache.incr(bucket_key)
            except ValueError:
                cache.set(bucket_key, 1, timeout=timeout)
                count = 1

        self._fanid_wait_seconds = max(0.0, remaining)
        return count <= self.num_requests

    def wait(self) -> float | None:
        return getattr(self, "_fanid_wait_seconds", None)


class LoginAccountRateThrottle(SimpleRateThrottle):
    """
    Limit attempts against the same account target regardless of origin, hashing the normalized
    address before using it as a cache key.
    """

    scope = "login_account"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        email = (request.data or {}).get("email") if hasattr(request, "data") else None

        if not isinstance(email, str) or not email.strip():
            return None

        digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()

        return self.cache_format % {
            "scope": self.scope,
            "ident": digest,
        }


def _refresh_token_from_request(request: Any) -> str | None:
    """Read a refresh token only from the transport declared by the client."""
    if not hasattr(request, "data"):
        return None

    data = request.data or {}
    client = data.get("client")

    if client == CLIENT_WEB:
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
    else:
        raw = data.get("refresh")

    if not isinstance(raw, str) or not raw.strip():
        return None

    return raw.strip()


class RefreshOriginRateThrottle(AtomicFixedWindowRateThrottle):
    """Rate-limit all refresh attempts from one network origin."""

    scope = "refresh_origin"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        ident = self.get_ident(request)
        if not ident:
            return None

        digest = hashlib.sha256(ident.encode("utf-8")).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": digest,
        }


class RefreshTokenRateThrottle(AtomicFixedWindowRateThrottle):
    """Rate-limit a presented token even when its signature is invalid."""

    scope = "refresh_token"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        raw = _refresh_token_from_request(request)
        if raw is None:
            return None

        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": digest,
        }


class RefreshSessionRateThrottle(AtomicFixedWindowRateThrottle):
    """
    Limit refresh rotations per session.

    The refresh token's stable `sid` claim keys the counter. Token source follows
    the HTTP contract for web and mobile clients. Missing or invalid tokens are
    left to the view/service so throttling never changes authentication semantics.
    """

    scope = "refresh"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        raw = _refresh_token_from_request(request)
        if raw is None:
            return None

        try:
            claims = decode_token(
                raw,
                expected_type=TokenType.REFRESH,
            )
        except TokenInvalidError:
            return None

        sid = claims.get("sid")
        if not isinstance(sid, str) or not sid.strip():
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": sid.strip(),
        }


class DeviceResetAccountRateThrottle(LoginAccountRateThrottle):
    """Limit reset requests per target account, reusing the same address normalization and hashing logic."""

    scope = "device_reset_account"


class PasswordResetAccountRateThrottle(LoginAccountRateThrottle):
    """Protect one mailbox from distributed requests while keeping only its SHA-256 key in cache."""

    scope = "password_reset_account"
