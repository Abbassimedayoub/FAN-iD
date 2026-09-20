"""
`TokenService` manages token issuance, rotation, and revocation.

The lower-level token module signs and verifies JWTs; this service attaches
tokens to persistent sessions and enforces strict single-use refresh rotation.

One login creates a token family represented by an `identity_session` row.
Each successful rotation replaces the current refresh `jti`. Replaying an old
refresh therefore revokes the entire family because the server cannot know
which holder is legitimate.

Rotation uses `SELECT ... FOR UPDATE` so concurrent refreshes cannot both read
and replace the same current `jti`. The second transaction observes the state
written by the first and correctly detects reuse.
"""

from __future__ import annotations

import dataclasses
import datetime
import logging
import uuid
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.observability.metrics import fanid_auth_token_reuse_detected_total

from ..constants import AUTH_LEVEL_PASSWORD, SESSION_REVOKED_ROTATION_REUSE
from ..models import Device, Session, User
from ..tokens import TokenInvalidError, TokenReuseDetectedError, TokenType, decode_token, encode_token

logger = logging.getLogger("fanid.identity")


class _ReuseSignal(Exception):
    """
    Internal signal that refresh-token reuse was detected.

    It never escapes this module. Its only purpose is to carry the finding
    outside the rotation transaction so the resulting revocation cannot be
    rolled back with that transaction.
    """

    def __init__(self, family_id: uuid.UUID) -> None:
        self.family_id = family_id
        super().__init__(str(family_id))


def _as_uuid(value: Any) -> uuid.UUID | None:
    """Convert a claim to UUID, or return `None` when it is not a valid UUID."""
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


@dataclasses.dataclass(frozen=True, slots=True)
class IssuedPair:
    """A token pair together with the session that owns it."""

    access: str
    refresh: str
    session: Session
    access_expires_at: datetime.datetime
    refresh_expires_at: datetime.datetime


def _access_lifetime() -> datetime.timedelta:
    return datetime.timedelta(minutes=int(settings.JWT_ACCESS_LIFETIME_MINUTES))


def _refresh_lifetime() -> datetime.timedelta:
    return datetime.timedelta(days=int(settings.JWT_REFRESH_LIFETIME_DAYS))


class TokenService:
    """Issue, rotate, and revoke authentication tokens."""

    # -- issuance -----------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def issue_pair(
        *,
        user: User,
        device: Device | None = None,
        client: str | None = None,
        family_id: uuid.UUID | None = None,
        auth_level: int = AUTH_LEVEL_PASSWORD,
        ip: str | None = None,
        user_agent: str = "",
        now: datetime.datetime | None = None,
    ) -> IssuedPair:
        """
        Open a session and issue its token pair.

        The session object is built before signing so its identifier can populate
        the `sid` claim and its `refresh_jti` can exactly match the issued
        refresh token.
        """
        moment = now or timezone.now()
        session = Session(
            user=user,
            device=device,
            client=client,
            family_id=family_id or uuid.uuid4(),
            auth_level=auth_level,
            ip=ip,
            # Truncate rather than reject an oversized User-Agent; it is audit metadata,
            # not a reason to refuse authentication.
            user_agent=(user_agent or "")[:255],
            issued_at=moment,
            last_used_at=moment,
        )
        pair = TokenService._sign_pair(session=session, user=user, device=device, now=moment)
        session.save()
        logger.info(
            "auth.session.opened",
            extra={"session_id": str(session.pk), "auth_level": auth_level},
        )
        return pair

    @staticmethod
    def _sign_pair(
        *,
        session: Session,
        user: User,
        device: Device | None,
        now: datetime.datetime,
    ) -> IssuedPair:
        """
        Sign a pair for an existing session object and align its token fields.

        The method mutates `session` without saving it so callers control whether
        the surrounding transaction performs an INSERT or targeted UPDATE.
        """
        refresh, refresh_jti, refresh_expires_at = encode_token(
            token_type=TokenType.REFRESH,
            subject=user.pk,
            lifetime=_refresh_lifetime(),
            claims={"family": str(session.family_id)},
            issued_at=now,
        )
        access, _, access_expires_at = encode_token(
            token_type=TokenType.ACCESS,
            subject=user.pk,
            lifetime=_access_lifetime(),
            claims={
                # The role is carried in the access token to avoid an extra lookup for every
                # authorization check; a refreshed token receives the latest role.
                "role": user.role.name,
                "did": str(device.pk) if device is not None else None,
                "sid": str(session.pk),
                "auth_level": session.auth_level,
            },
            issued_at=now,
        )
        session.refresh_jti = refresh_jti
        session.expires_at = refresh_expires_at
        session.last_used_at = now
        return IssuedPair(
            access=access,
            refresh=refresh,
            session=session,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )

    # -- rotation -----------------------------------------------------------

    @staticmethod
    def rotate(raw_refresh: str, *, now: datetime.datetime | None = None) -> IssuedPair:
        """
        Consume one refresh token and issue a new one with strict single use.

        If the presented token was already rotated, revoke the family and raise
        `TokenReuseDetectedError`.
        """
        claims = decode_token(raw_refresh, expected_type=TokenType.REFRESH)
        moment = now or timezone.now()

        try:
            with transaction.atomic():
                session = TokenService._lock_current_session(claims, moment)
                pair = TokenService._sign_pair(
                    session=session,
                    user=session.user,
                    device=session.device,
                    now=moment,
                )
                session.save(update_fields=["refresh_jti", "expires_at", "last_used_at"])
        except _ReuseSignal as signal:
            # Revocation must survive the failed rotation transaction. Revoking inside
            # the atomic block would be rolled back with the exception, leaving a
            # compromised family alive. Carry the finding outside first, then revoke.
            revoked = TokenService.revoke_family(signal.family_id, SESSION_REVOKED_ROTATION_REUSE, now=moment)
            fanid_auth_token_reuse_detected_total.inc()
            logger.warning(
                "auth.token.reuse_detected",
                extra={"family_id": str(signal.family_id), "sessions_revoked": revoked},
            )
            raise TokenReuseDetectedError() from None

        logger.info("auth.token.rotated", extra={"session_id": str(session.pk)})
        return pair

    @staticmethod
    def _lock_current_session(claims: dict[str, Any], now: datetime.datetime) -> Session:
        """
        Lock the session whose current refresh token matches the presented claims.

        `SELECT ... FOR UPDATE` serializes concurrent rotations. After waiting,
        the losing transaction re-evaluates the row condition and sees that the
        winning rotation already changed `refresh_jti`.
        """
        # Convert identifiers before querying so malformed UUID claims map to token
        # invalidity rather than surfacing as database-field validation errors.
        jti = _as_uuid(claims.get("jti"))
        family_id = _as_uuid(claims.get("family"))
        if jti is None:
            raise TokenInvalidError()

        try:
            return (
                # Lock only the session row. The nullable device relation uses a LEFT JOIN,
                # and locking joined rows would either be rejected by PostgreSQL or
                # create unnecessary contention on shared related rows.
                Session.objects.select_for_update(of=("self",))
                .select_related("user", "user__role", "device")
                .get(refresh_jti=jti, revoked_at__isnull=True, expires_at__gt=now)
            )
        except Session.DoesNotExist:
            pass

        if family_id and Session.objects.filter(family_id=family_id, revoked_at__isnull=True).exists():
            # The token is validly signed and its family is still live, but it is no
            # longer current. It was already rotated; revoke outside this transaction.
            raise _ReuseSignal(family_id)

        # Unknown or already-revoked families get the same opaque invalid-token result;
        # do not reveal session state to the caller.
        raise TokenInvalidError()

    # -- revocation ---------------------------------------------------------

    @staticmethod
    def revoke_family(
        family_id: uuid.UUID,
        reason: str,
        *,
        now: datetime.datetime | None = None,
    ) -> int:
        """
        Revoke the full lineage created by one login and return the row count.

        A single UPDATE keeps emergency revocation atomic instead of relying on
        an interruptible Python loop.
        """
        return Session.objects.filter(family_id=family_id, revoked_at__isnull=True).update(
            revoked_at=now or timezone.now(), revoked_reason=reason
        )

    @staticmethod
    def revoke_session(session: Session, reason: str, *, now: datetime.datetime | None = None) -> int:
        """Revoke one specific session."""
        return Session.objects.filter(pk=session.pk, revoked_at__isnull=True).update(
            revoked_at=now or timezone.now(), revoked_reason=reason
        )

    @staticmethod
    def revoke_all_for_user(user: User, reason: str, *, now: datetime.datetime | None = None) -> int:
        """
        Revoke every active session for an account.

        Password changes use this so sessions authenticated with the previous
        credential cannot remain active.
        """
        return Session.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=now or timezone.now(), revoked_reason=reason
        )
