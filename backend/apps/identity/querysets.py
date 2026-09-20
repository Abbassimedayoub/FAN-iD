"""
QuerySets for the `identity` context.

They centralize definitions such as "active device" and "valid session" so
services do not duplicate them and accidentally diverge on filters such as
`expires_at` or `revoked_at`.
"""

from datetime import datetime
from typing import Any

from django.db import models
from django.utils import timezone


class DeviceQuerySet(models.QuerySet):
    def active(self) -> "DeviceQuerySet":
        """
        Return non-revoked devices. At most one may exist per account, enforced
        by a partial uniqueness constraint in the database.
        """
        return self.filter(revoked_at__isnull=True)

    def revoked(self) -> "DeviceQuerySet":
        return self.filter(revoked_at__isnull=False)

    def for_user(self, user: Any) -> "DeviceQuerySet":
        return self.filter(user=user)

    def stale(self, before: datetime) -> "DeviceQuerySet":
        """Return devices revoked before `before`, for retention cleanup."""
        return self.revoked().filter(revoked_at__lt=before)


class SessionQuerySet(models.QuerySet):
    def active(self) -> "SessionQuerySet":
        """
        Return usable sessions: neither revoked nor expired.

        Both conditions matter. Checking only revocation would admit an expired
        refresh session; checking only expiry would admit a session explicitly
        revoked after token reuse.
        """
        return self.filter(revoked_at__isnull=True, expires_at__gt=timezone.now())

    def expired(self) -> "SessionQuerySet":
        return self.filter(expires_at__lte=timezone.now())

    def for_user(self, user: Any) -> "SessionQuerySet":
        return self.filter(user=user)

    def for_family(self, family_id: Any) -> "SessionQuerySet":
        """Return the full session lineage created from one login."""
        return self.filter(family_id=family_id)


class MfaChallengeQuerySet(models.QuerySet):
    def open(self) -> "MfaChallengeQuerySet":
        """
        Return challenges that are still usable: unconsumed, unexpired, and
        below the attempt limit.
        """
        return self.filter(
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
            attempts__lt=models.F("max_attempts"),
        )

    def for_purpose(self, user: Any, purpose: str) -> "MfaChallengeQuerySet":
        return self.filter(user=user, purpose=purpose)
