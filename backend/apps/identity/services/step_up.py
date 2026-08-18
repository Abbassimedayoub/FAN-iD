"""
Verification renforcee de la session courante.

Le code OTP eleve uniquement la session qui a demande le challenge.
Aucun nouveau JWT n'est emis : JWTAuthentication relit auth_level depuis
la session a chaque requete.
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

from ..constants import AUTH_LEVEL_STEP_UP, MFA_PURPOSE_STEP_UP, OTP_TTL_MINUTES
from ..exceptions import OtpInvalidError, OtpMaxAttemptsError
from ..models import MfaChallenge, Session, User
from ..tokens import TokenInvalidError

logger = logging.getLogger("fanid.identity")

CODE_DIGITS = 6


def _hash_code(session_id: uuid.UUID, code: str) -> str:
    """
    Lie cryptographiquement le code a la session qui l'a demande.

    MfaChallenge ne porte volontairement pas de FK session. Inclure le sid
    dans le digest empeche qu'un code demande depuis une session A eleve
    une session B du meme utilisateur.
    """
    raw = f"{session_id}:{code}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True, slots=True)
class StepUpRequestResult:
    challenge_id: uuid.UUID


class StepUpService:
    """Emission et confirmation du challenge STEP_UP."""

    def __init__(self, *, sender: NotificationSender) -> None:
        self._sender = sender

    def request(
        self,
        *,
        user: User,
        session_id: uuid.UUID,
    ) -> StepUpRequestResult:
        code = f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"
        now = timezone.now()

        with transaction.atomic():
            # Le verrou utilisateur serialise les demandes concurrentes :
            # un seul challenge STEP_UP reste utilisable pour ce compte.
            locked_user = User.objects.select_for_update().get(pk=user.pk)

            session = (
                Session.objects.select_for_update().active().filter(pk=session_id, user=locked_user).first()
            )
            if session is None:
                raise TokenInvalidError()

            invalidated = (
                MfaChallenge.objects.for_purpose(
                    locked_user,
                    MFA_PURPOSE_STEP_UP,
                )
                .filter(consumed_at__isnull=True)
                .update(consumed_at=now)
            )

            challenge = MfaChallenge.objects.create(
                user=locked_user,
                purpose=MFA_PURPOSE_STEP_UP,
                code_hash=_hash_code(session.pk, code),
                expires_at=now + datetime.timedelta(minutes=int(OTP_TTL_MINUTES)),
            )

        self._send(locked_user, code)

        logger.info(
            "auth.step_up.requested",
            extra={
                "user_id": str(locked_user.pk),
                "session_id": str(session_id),
                "invalidated": invalidated,
            },
        )

        return StepUpRequestResult(challenge_id=challenge.pk)

    def _send(self, user: User, code: str) -> None:
        try:
            self._sender.send_email(
                to=user.email,
                subject="FAN iD — code de verification renforcee",
                body=(
                    f"Votre code de verification est {code}. "
                    f"Il expire dans {OTP_TTL_MINUTES} minutes. "
                    "Si vous n etes pas a l origine de cette demande, "
                    "ignorez ce message."
                ),
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "auth.step_up.send_failed",
                extra={"user_id": str(user.pk)},
            )

    def confirm(
        self,
        *,
        user: User,
        session_id: uuid.UUID,
        challenge_id: uuid.UUID,
        code: str,
    ) -> None:
        outcome = self._settle(
            user=user,
            session_id=session_id,
            challenge_id=challenge_id,
            code=code,
        )

        # Important : lever APRES transaction.atomic(), sinon l'increment
        # attempts serait rollbacke.
        if outcome == "exhausted":
            raise OtpMaxAttemptsError()
        if outcome == "invalid":
            raise OtpInvalidError()

    def _settle(
        self,
        *,
        user: User,
        session_id: uuid.UUID,
        challenge_id: Any,
        code: str,
    ) -> str:
        now = timezone.now()

        with transaction.atomic():
            challenge = (
                MfaChallenge.objects.select_for_update(of=("self",))
                .filter(
                    pk=challenge_id,
                    user=user,
                    purpose=MFA_PURPOSE_STEP_UP,
                )
                .first()
            )

            unusable = (
                challenge is None
                or challenge.consumed_at is not None
                or challenge.expires_at <= now
                or challenge.attempts >= challenge.max_attempts
            )

            if unusable or challenge is None:
                logger.info(
                    "auth.step_up.refused",
                    extra={"reason": "challenge_unusable"},
                )
                return "invalid"

            expected_hash = _hash_code(session_id, code)

            if not secrets.compare_digest(
                challenge.code_hash,
                expected_hash,
            ):
                challenge.attempts += 1
                exhausted = challenge.attempts >= challenge.max_attempts

                if exhausted:
                    challenge.consumed_at = now

                challenge.save(
                    update_fields=["attempts", "consumed_at"],
                )

                logger.warning(
                    "auth.step_up.refused",
                    extra={
                        "reason": "bad_code",
                        "attempts": challenge.attempts,
                    },
                )

                return "exhausted" if exhausted else "invalid"

            # On verrouille exactement la session courante.
            session = (
                Session.objects.select_for_update()
                .active()
                .filter(
                    pk=session_id,
                    user=user,
                )
                .first()
            )

            if session is None:
                # La session a ete revoquee entre authentification et
                # confirmation. Le challenge ne doit plus etre reutilisable.
                challenge.consumed_at = now
                challenge.save(update_fields=["consumed_at"])
                return "invalid"

            challenge.consumed_at = now
            challenge.save(update_fields=["consumed_at"])

            if session.auth_level < AUTH_LEVEL_STEP_UP:
                session.auth_level = AUTH_LEVEL_STEP_UP
                session.save(update_fields=["auth_level"])

        logger.info(
            "auth.step_up.confirmed",
            extra={
                "user_id": str(user.pk),
                "session_id": str(session_id),
            },
        )

        return "ok"
