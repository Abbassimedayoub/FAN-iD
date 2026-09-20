"""
`DeviceBindingService` enforces at most one active device per account.

The device fingerprint is computed client-side and treated as opaque by the
server. The server validates only its canonical format and does not substitute
IP addresses, User-Agent strings, or behavioral fingerprinting.

ORGANIZER and ADMIN roles are intentionally exempt from the single-device lock.
They still retain refresh-token rotation, reuse detection, and family
revocation.
"""

from __future__ import annotations

import datetime
import re
import secrets
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.interfaces import DeviceLockBackend

from ..constants import DEVICE_PLATFORMS, FINGERPRINT_PATTERN, ROLE_ADMIN, ROLE_ORGANIZER
from ..exceptions import DeviceLockedError, DeviceMismatchError, InvalidFingerprintError
from ..models import Device, User

#: Roles exempt from the device lock.
DEVICE_EXEMPT_ROLES: tuple[str, ...] = (ROLE_ORGANIZER, ROLE_ADMIN)

#: Cache-lock lifetime. After expiry, truth is read from the database; an expired
#: cache entry grants no additional rights.
LOCK_TTL_SECONDS = 3600

#: Refresh `last_seen_at` only after this interval to avoid a database write on
#: every API request.
LAST_SEEN_REFRESH = datetime.timedelta(hours=1)

_FINGERPRINT = re.compile(FINGERPRINT_PATTERN)


def _partial_label(device: Device) -> str:
    """Return a truncated device label suitable for a `DEVICE_LOCKED` response."""
    label = device.label or device.platform
    return label if len(label) <= 12 else f"{label[:12]}…"


class DeviceBindingService:
    """Bind one device to an account and reject competing devices."""

    def __init__(self, lock: DeviceLockBackend) -> None:
        # The lock backend is injected so tests can simulate Redis failure and exercise
        # fallback behavior deterministically.
        self._lock = lock

    # -- validation ---------------------------------------------------------

    @staticmethod
    def validate_fingerprint(fingerprint: str) -> str:
        """
        Require exactly 64 lowercase hexadecimal characters.

        Reject rather than normalize so one physical device cannot acquire two
        canonical identities that differ only by case.
        """
        if not isinstance(fingerprint, str) or not _FINGERPRINT.fullmatch(fingerprint):
            raise InvalidFingerprintError()
        return fingerprint

    @staticmethod
    def is_exempt(user: User) -> bool:
        return user.role.name in DEVICE_EXEMPT_ROLES

    # -- binding ------------------------------------------------------------

    def bind(
        self,
        *,
        user: User,
        fingerprint: str,
        platform: str,
        label: str = "",
        now: datetime.datetime | None = None,
    ) -> Device | None:
        """Return the bound device, or `None` for an exempt role; reject another active device."""
        if self.is_exempt(user):
            return None

        self.validate_fingerprint(fingerprint)
        if platform not in DEVICE_PLATFORMS:
            raise InvalidFingerprintError(details={"platform": list(DEVICE_PLATFORMS)})

        moment = now or timezone.now()
        active = Device.objects.active().for_user(user).first()

        if active is not None:
            if active.fingerprint != fingerprint:
                raise DeviceLockedError(
                    details={
                        "active_device_label": _partial_label(active),
                        "bound_at": active.bound_at.isoformat(),
                        # Device reset is available as the recovery path for a competing active device.
                        "reset_available": True,
                    }
                )
            self._touch(active, moment)
            self._lock.acquire(str(user.pk), str(active.pk), LOCK_TTL_SECONDS)
            return active

        return self._create(user=user, fingerprint=fingerprint, platform=platform, label=label)

    def _create(self, *, user: User, fingerprint: str, platform: str, label: str) -> Device:
        """
        Create the device and let the database arbitrate concurrent creations.

        The partial unique constraint on active devices is the race-safe source
        of truth when two connections attempt to bind simultaneously.
        """
        try:
            with transaction.atomic():
                device = Device.objects.create(
                    user=user,
                    fingerprint=fingerprint,
                    platform=platform,
                    label=label[:60],
                )
        except IntegrityError as exc:
            # Another device won the concurrent bind. Return the same result as a later request.
            active = Device.objects.active().for_user(user).first()
            details: dict[str, Any] = {"reset_available": True}
            if active is not None:
                details["active_device_label"] = _partial_label(active)
                details["bound_at"] = active.bound_at.isoformat()
            raise DeviceLockedError(details=details) from exc

        self._lock.acquire(str(user.pk), str(device.pk), LOCK_TTL_SECONDS)
        return device

    def _touch(self, device: Device, now: datetime.datetime) -> None:
        """Refresh `last_seen_at` at most once per hour."""
        if now - device.last_seen_at < LAST_SEEN_REFRESH:
            return
        Device.objects.filter(pk=device.pk).update(last_seen_at=now)
        device.last_seen_at = now

    # -- per-request verification -------------------------------------------

    def assert_matches(self, *, user: User, device_id: Any) -> Device | None:
        """
        Verify that the token's `did` identifies the account's active device.

        The cache handles the nominal hot path; if it is empty or unavailable,
        the database remains the source of truth. A mismatch is authentication
        failure because a token used from another device may be stolen.
        """
        if self.is_exempt(user):
            return None

        expected = self._lock.get_active(str(user.pk))
        if expected is None:
            # Cold or expired cache: read the authoritative state from the database.
            device = Device.objects.active().for_user(user).first()
            if device is None:
                # With no active device, an absent `did` is consistent. A present `did` points
                # to a no-longer-active device and must be rejected.
                if device_id is None:
                    return None
                raise DeviceMismatchError()
            expected = str(device.pk)
            self._lock.acquire(str(user.pk), expected, LOCK_TTL_SECONDS)

        if device_id is None or str(device_id) != expected:
            raise DeviceMismatchError()

        return Device.objects.active().for_user(user).filter(pk=expected).first()

    def assert_fingerprint(self, *, device: Device, fingerprint: str | None) -> None:
        """
        Verify that a presented fingerprint matches the session device.

        Refresh flows use this check so a stolen refresh token cannot extend a
        session from another device. Revoked devices are rejected immediately,
        and the fingerprint comparison uses constant-time comparison.
        """
        if device.revoked_at is not None:
            raise DeviceMismatchError()
        # Compare bytes because `compare_digest` can reject non-ASCII strings. A
        # malformed fingerprint simply fails to match and receives the same
        # authentication error rather than a distinct oracle.
        presented = (fingerprint or "").encode("utf-8")
        if not secrets.compare_digest(device.fingerprint.encode("utf-8"), presented):
            raise DeviceMismatchError()

    # -- revocation ---------------------------------------------------------

    def revoke(self, device: Device, reason: str, *, now: datetime.datetime | None = None) -> int:
        """
        Revoke the device and release its cache lock.

        Persist revocation first and clear the cache second so another bind
        cannot observe an empty cache while the old device is still active in
        the database.
        """
        updated = Device.objects.filter(pk=device.pk, revoked_at__isnull=True).update(
            revoked_at=now or timezone.now(), revoked_reason=reason
        )
        if updated:
            self._lock.release(str(device.user_id))
        return updated
