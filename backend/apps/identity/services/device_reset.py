"""
`DeviceResetService` unbinds a device when normal authentication is no longer
possible.

The reset endpoints are intentionally usable without an authenticated session:
a user locked out by the device binding has no token to present. The request
therefore proves credentials, while confirmation proves possession of a
single-use code.

The flow is designed to avoid account-existence oracles, lost attempt counters,
and code leakage. Unknown credentials still pay the decoy-hash cost, challenge
identifiers are always returned, failed attempts commit before public errors are
raised, and only code digests are stored.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import logging
import secrets
import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.interfaces import NotificationSender
from apps.core.observability.metrics import fanid_device_reset_total
from apps.core.outbox.publisher import publish_event

from ..constants import (
    DEVICE_REVOKED_USER_RESET,
    MFA_PURPOSE_DEVICE_RESET,
    OTP_TTL_MINUTES,
    SESSION_REVOKED_DEVICE_RESET,
)
from ..events import (
    AGGREGATE_USER,
    DEVICE_RESET_CONFIRMED,
    DEVICE_RESET_REQUESTED,
    device_reset_confirmed_payload,
    device_reset_requested_payload,
)
from ..exceptions import OtpInvalidError, OtpMaxAttemptsError
from ..models import Device, MfaChallenge, User
from .authentication import _decoy_hash
from .devices import DeviceBindingService
from .tokens import TokenService

logger = logging.getLogger("fanid.identity")

#: Six-digit code intended for manual entry. Security comes from the bounded
#: attempt count as well as the one-time challenge lifetime.
CODE_DIGITS = 6


def _hash_code(code: str) -> str:
    """Return the lowercase hexadecimal SHA-256 digest required by the constraint."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True, slots=True)
class ResetRequestResult:
    """
    Result of a reset request.

    `challenge_id` is returned in every case. `created` is internal state used
    only to decide whether notification and event side effects should occur.
    """

    challenge_id: uuid.UUID
    created: bool


@dataclasses.dataclass(frozen=True, slots=True)
class ResetConfirmResult:
    device_revoked: bool
    sessions_revoked: int


class DeviceResetService:
    """Issue and verify device-reset codes."""

    def __init__(self, *, binding: DeviceBindingService, sender: NotificationSender) -> None:
        self._binding = binding
        self._sender = sender

    # -- request -------------------------------------------------------------

    def request(self, *, email: str, password: str) -> ResetRequestResult:
        """
        Issue a reset code, or simulate the request for invalid credentials.

        The decoy path writes nothing and sends nothing, while still paying the
        credential-verification cost.
        """
        user = self._verify(email, password)
        if user is None:
            # Return a random, unpersisted identifier. Confirmation cannot distinguish this
            # path from an invalid code on a real challenge.
            return ResetRequestResult(challenge_id=uuid.uuid4(), created=False)

        code = f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"
        now = timezone.now()

        with transaction.atomic():
            # Lock the account row so concurrent requests serialize and cannot create
            # several simultaneously valid reset challenges.
            User.objects.select_for_update().get(pk=user.pk)

            invalidated = (
                MfaChallenge.objects.for_purpose(user, MFA_PURPOSE_DEVICE_RESET)
                .filter(consumed_at__isnull=True)
                .update(consumed_at=now)
            )

            challenge = MfaChallenge.objects.create(
                user=user,
                purpose=MFA_PURPOSE_DEVICE_RESET,
                code_hash=_hash_code(code),
                expires_at=now + datetime.timedelta(minutes=int(OTP_TTL_MINUTES)),
            )
            active = Device.objects.active().for_user(user).first()
            publish_event(
                event_type=DEVICE_RESET_REQUESTED,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=user.pk,
                actor_id=user.pk,
                payload=device_reset_requested_payload(device_bound=active is not None),
            )

        # Send only after commit so a rolled-back transaction cannot email a nonexistent
        # code. Delivery failure is logged without changing the public response.
        self._send(user, code)

        logger.info(
            "device.reset.requested",
            extra={"user_id": str(user.pk), "invalidated": invalidated},
        )
        return ResetRequestResult(challenge_id=challenge.pk, created=True)

    def _verify(self, email: str, password: str) -> User | None:
        """
        Apply the same opaque credential checks and comparable cost as login.

        Reuse the authentication module's decoy hash so both flows stay aligned
        when password-hasher parameters change.
        """
        user = User.objects.select_related("role").filter(email=email).first()
        if user is None:
            from django.contrib.auth.hashers import check_password

            check_password(password, _decoy_hash())
            logger.info("device.reset.refused", extra={"reason": "unknown_email"})
            return None
        if not user.check_password(password):
            logger.info("device.reset.refused", extra={"reason": "bad_password"})
            return None
        if not user.is_active or user.anonymized_at is not None:
            logger.warning("device.reset.refused", extra={"reason": "inactive_account"})
            return None
        return user

    def _send(self, user: User, code: str) -> None:
        try:
            self._sender.send_email(
                to=user.email,
                subject="FAN iD — code de reinitialisation d appareil",
                body=(
                    f"Votre code de reinitialisation est {code}. "
                    f"Il expire dans {OTP_TTL_MINUTES} minutes. "
                    "Si vous n etes pas a l origine de cette demande, ignorez ce message."
                ),
            )
        except Exception:  # noqa: BLE001 - notification failure must not reveal account state
            logger.exception("device.reset.send_failed", extra={"user_id": str(user.pk)})

    # -- confirmation --------------------------------------------------------

    def confirm(self, *, challenge_id: uuid.UUID, code: str) -> ResetConfirmResult:
        """
        Verify the code, unbind the device, and revoke sessions.

        Failed-attempt writes commit before the public exception is raised;
        otherwise the transaction rollback would erase the increment and make
        the attempt limit ineffective.
        """
        outcome, result = self._settle(challenge_id, code)

        if outcome == "exhausted":
            fanid_device_reset_total.labels(result="exhausted").inc()
            raise OtpMaxAttemptsError()
        if outcome == "invalid":
            fanid_device_reset_total.labels(result="invalid").inc()
            raise OtpInvalidError()

        fanid_device_reset_total.labels(result="success").inc()
        assert result is not None
        return result

    def _settle(self, challenge_id: Any, code: str) -> tuple[str, ResetConfirmResult | None]:
        """Apply all state changes and return an outcome without raising a public error."""
        now = timezone.now()

        with transaction.atomic():
            challenge = (
                # Lock only the challenge row. Avoid locking joined role data, which would add
                # unnecessary contention and can conflict with nullable joins.
                MfaChallenge.objects.select_for_update(of=("self",))
                .select_related("user", "user__role")
                .filter(pk=challenge_id, purpose=MFA_PURPOSE_DEVICE_RESET)
                .first()
            )

            unusable = (
                challenge is None
                or challenge.consumed_at is not None
                or challenge.expires_at <= now
                or challenge.attempts >= challenge.max_attempts
            )
            if unusable or challenge is None:
                logger.info("device.reset.refused", extra={"reason": "challenge_unusable"})
                return "invalid", None

            if not secrets.compare_digest(challenge.code_hash, _hash_code(code)):
                challenge.attempts += 1
                exhausted = challenge.attempts >= challenge.max_attempts
                if exhausted:
                    challenge.consumed_at = now
                challenge.save(update_fields=["attempts", "consumed_at"])
                logger.warning(
                    "device.reset.refused",
                    extra={"reason": "bad_code", "attempts": challenge.attempts},
                )
                return ("exhausted" if exhausted else "invalid"), None

            challenge.consumed_at = now
            challenge.save(update_fields=["consumed_at"])

            user = challenge.user
            active = Device.objects.active().for_user(user).first()
            device_revoked = False
            if active is not None:
                device_revoked = bool(self._binding.revoke(active, DEVICE_REVOKED_USER_RESET, now=now))

            # Revoke every session, not only sessions bound to the device, because this is
            # an account-recovery path for a presumed lost or compromised device.
            sessions_revoked = TokenService.revoke_all_for_user(user, SESSION_REVOKED_DEVICE_RESET, now=now)

            publish_event(
                event_type=DEVICE_RESET_CONFIRMED,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=user.pk,
                actor_id=user.pk,
                payload=device_reset_confirmed_payload(
                    device_revoked=device_revoked, sessions_revoked=sessions_revoked
                ),
            )

        logger.info(
            "device.reset.confirmed",
            extra={"device_revoked": device_revoked, "sessions_revoked": sessions_revoked},
        )
        return "ok", ResetConfirmResult(device_revoked=device_revoked, sessions_revoked=sessions_revoked)
