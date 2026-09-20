"""
Device-lock composition using Redis as a fast path and PostgreSQL as the source
of truth.

The active device is defined by the database constraint on `identity_device`.
Redis caches the decision to avoid a database read on the hottest request path;
if Redis fails, the implementation falls back to authoritative database state
rather than failing open.

The generic device-lock port lives in core, while this fallback lives in
identity because it must read identity-owned tables. The resilient composition
therefore belongs to the context that owns the business rule.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from apps.core.interfaces import DeviceLockBackend

from .models import Device

logger = logging.getLogger("fanid.identity")

try:  # pragma: no cover - depend de l environnement d execution
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover - Redis absent : le repli reste utilisable

    class RedisError(Exception):  # type: ignore[no-redef]
        """Fallback exception type used when the Redis client package is unavailable."""


#: Failures considered transient and eligible for database fallback.
#:
#: Keep this tuple narrow: catching every Exception would disguise programming
#: errors as infrastructure outages.
TRANSIENT_FAILURES: tuple[type[BaseException], ...] = (RedisError, OSError, TimeoutError)


class PostgresDeviceLock(DeviceLockBackend):
    """Database fallback using the authoritative active-device constraint rather than a second lock table."""

    def acquire(self, user_id: str, device_id: str, ttl_seconds: int) -> bool:
        """The database fallback ignores TTL because a persisted device binding remains valid until an explicit revocation."""
        active = self.get_active(user_id)
        return active is None or active == str(device_id)

    def get_active(self, user_id: str) -> Any | None:
        device_id = Device.objects.active().filter(user_id=user_id).values_list("id", flat=True).first()
        return str(device_id) if device_id is not None else None

    def release(self, user_id: str) -> None:
        """Deliberate no-op: database binding release is a business revocation operation, not a cache unlock."""
        return None


class ResilientDeviceLock(DeviceLockBackend):
    """Primary device lock with fail-closed database fallback for transient cache failures."""

    def __init__(self, primary: DeviceLockBackend, fallback: DeviceLockBackend) -> None:
        self._primary = primary
        self._fallback = fallback

    def _with_fallback(self, operation: str, *args: Any) -> Any:
        try:
            return getattr(self._primary, operation)(*args)
        except TRANSIENT_FAILURES as exc:
            # Warning rather than error: fallback preserves correctness but indicates a
            # degraded fast path.
            logger.warning(
                "device_lock.fallback_engaged",
                extra={"lock_operation": operation, "failure": type(exc).__name__},
            )
            return getattr(self._fallback, operation)(*args)

    def acquire(self, user_id: str, device_id: str, ttl_seconds: int) -> bool:
        return bool(self._with_fallback("acquire", user_id, device_id, ttl_seconds))

    def get_active(self, user_id: str) -> Any | None:
        return self._with_fallback("get_active", user_id)

    def release(self, user_id: str) -> None:
        self._with_fallback("release", user_id)


def build_device_lock() -> DeviceLockBackend:
    """Build the real lock lazily: Redis primary with PostgreSQL fallback."""
    import redis

    client = redis.Redis.from_url(settings.REDIS_LOCK_URL)
    from apps.core.adapters.device_lock import RedisDeviceLock

    return ResilientDeviceLock(primary=RedisDeviceLock(client), fallback=PostgresDeviceLock())
