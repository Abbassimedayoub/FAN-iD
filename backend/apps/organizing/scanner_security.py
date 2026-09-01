from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.core.exceptions import (
    ConflictError,
    NotFoundBusinessError,
    RateLimitError,
    StaleResourceError,
    ValidationBusinessError,
)

from .models import Organizer, Scanner, ScannerRevocationChallenge

SCANNER_SECURITY_OTP_TTL_MINUTES = 5
SCANNER_SECURITY_OTP_MAX_ATTEMPTS = 5

SCANNER_SECURITY_ACTION_REVOKE = "REVOKE"
SCANNER_SECURITY_ACTION_LEAVE_ACCEPT = "LEAVE_ACCEPT"
SCANNER_SECURITY_ACTION_LEAVE_REQUEST = "LEAVE_REQUEST"

SCANNER_SECURITY_ACTIONS = {
    SCANNER_SECURITY_ACTION_REVOKE,
    SCANNER_SECURITY_ACTION_LEAVE_ACCEPT,
    SCANNER_SECURITY_ACTION_LEAVE_REQUEST,
}


class ScannerSecurityOtpInvalidError(
    ValidationBusinessError,
):
    default_code = "OTP_INVALID"
    default_message = "Code invalide ou expire."


class ScannerSecurityOtpMaxAttemptsError(
    RateLimitError,
):
    default_code = "OTP_MAX_ATTEMPTS"
    default_message = "Trop de tentatives. " "Demandez un nouveau code."


@dataclass(frozen=True)
class ScannerSecurityChallengeResult:
    challenge_id: uuid.UUID
    expires_in_seconds: int


def derive_scanner_security_code(
    challenge_id: uuid.UUID,
) -> str:
    digest = salted_hmac(
        "fanid.organizing.scanner-security-otp.v1",
        str(challenge_id),
        secret=str(settings.SECRET_KEY),
        algorithm="sha256",
    ).digest()

    number = int.from_bytes(digest[:8], "big") % 1_000_000

    return f"{number:06d}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(
        code.encode("utf-8"),
    ).hexdigest()


class ScannerSecurityService:
    @staticmethod
    def request(
        *,
        organizer: Organizer,
        scanner_id: uuid.UUID,
        requested_by_id: Any,
        action: str,
    ) -> ScannerSecurityChallengeResult:
        if action not in SCANNER_SECURITY_ACTIONS:
            raise ValueError("unsupported scanner security action")

        now = timezone.now()

        with transaction.atomic():
            scanner = (
                Scanner.objects.select_for_update()
                .filter(
                    pk=scanner_id,
                    organizer=organizer,
                    archived_at__isnull=True,
                )
                .first()
            )

            if scanner is None:
                raise NotFoundBusinessError()

            if action == SCANNER_SECURITY_ACTION_REVOKE:
                if scanner.status in {
                    "INVITATION_CANCELLED",
                    "DELETED",
                    "LEAVE_REQUESTED",
                }:
                    raise ConflictError(
                        code="SCANNER_REVOCATION_NOT_ALLOWED",
                        message=("Ce scanner ne peut pas être retiré " "depuis cette action."),
                    )
            elif action == SCANNER_SECURITY_ACTION_LEAVE_ACCEPT:
                if scanner.status != "LEAVE_REQUESTED":
                    raise ConflictError(
                        code="SCANNER_LEAVE_REQUEST_NOT_PENDING",
                        message=("Aucune demande de départ " "n'est en attente."),
                    )
            elif action == SCANNER_SECURITY_ACTION_LEAVE_REQUEST:
                if scanner.status == "LEAVE_REQUESTED":
                    raise ConflictError(
                        code="SCANNER_LEAVE_ALREADY_REQUESTED",
                        message=("Une demande de départ est " "déjà en attente."),
                    )

                if scanner.status != "ACTIVE":
                    raise ConflictError(
                        code="SCANNER_LEAVE_NOT_ALLOWED",
                        message=(
                            "La demande de départ est disponible " "uniquement pour un compte scanner actif."
                        ),
                    )

            # Toute nouvelle demande invalide immédiatement
            # les challenges encore ouverts pour cette même action.
            ScannerRevocationChallenge.objects.filter(
                organizer=organizer,
                scanner=scanner,
                requested_by_id=requested_by_id,
                action=action,
                consumed_at__isnull=True,
            ).update(
                consumed_at=now,
            )

            challenge_id = uuid.uuid4()
            code = derive_scanner_security_code(
                challenge_id,
            )

            challenge = ScannerRevocationChallenge.objects.create(
                id=challenge_id,
                organizer=organizer,
                scanner=scanner,
                requested_by_id=requested_by_id,
                action=action,
                code_hash=_hash_code(code),
                max_attempts=SCANNER_SECURITY_OTP_MAX_ATTEMPTS,
                expires_at=(
                    now
                    + timezone.timedelta(
                        minutes=SCANNER_SECURITY_OTP_TTL_MINUTES,
                    )
                ),
            )

        from .scanner_security_tasks import send_scanner_security_code_email

        transaction.on_commit(
            lambda: send_scanner_security_code_email.delay(
                challenge_id=str(challenge.pk),
            )
        )

        return ScannerSecurityChallengeResult(
            challenge_id=challenge.pk,
            expires_in_seconds=(SCANNER_SECURITY_OTP_TTL_MINUTES * 60),
        )

    @staticmethod
    def consume_and_run(
        *,
        organizer: Organizer,
        scanner_id: uuid.UUID,
        requested_by_id: Any,
        challenge_id: uuid.UUID,
        code: str,
        action: str,
        expected_version: int,
        operation: Callable[[], Any],
    ) -> Any:
        """
        Vérifie la version avant de consommer l'OTP puis exécute
        l'action destructive dans la même transaction.

        Une erreur métier après un OTP valide annule donc aussi la
        consommation du code.

        Les erreurs OTP sont capturées dans la transaction afin que
        les compteurs de mauvaises tentatives restent persistés.
        """
        otp_error: Exception | None = None
        result: Any = None

        with transaction.atomic():
            scanner = (
                Scanner.objects.select_for_update()
                .filter(
                    pk=scanner_id,
                    organizer=organizer,
                )
                .first()
            )

            if scanner is None:
                raise NotFoundBusinessError()

            if scanner.version != expected_version:
                raise StaleResourceError(
                    details={
                        "current_version": scanner.version,
                    },
                )

            try:
                ScannerSecurityService.consume(
                    organizer=organizer,
                    scanner_id=scanner_id,
                    requested_by_id=requested_by_id,
                    challenge_id=challenge_id,
                    code=code,
                    action=action,
                )
            except (
                ScannerSecurityOtpInvalidError,
                ScannerSecurityOtpMaxAttemptsError,
            ) as exc:
                otp_error = exc

            if otp_error is None:
                result = operation()

        if otp_error is not None:
            raise otp_error

        return result

    @staticmethod
    def consume(
        *,
        organizer: Organizer,
        scanner_id: uuid.UUID,
        requested_by_id: Any,
        challenge_id: uuid.UUID,
        code: str,
        action: str,
    ) -> None:
        now = timezone.now()
        error_to_raise = None

        with transaction.atomic():
            challenge = (
                ScannerRevocationChallenge.objects.select_for_update()
                .filter(
                    pk=challenge_id,
                    organizer=organizer,
                    scanner_id=scanner_id,
                    requested_by_id=requested_by_id,
                    action=action,
                )
                .first()
            )

            if challenge is None or challenge.consumed_at is not None or challenge.expires_at <= now:
                raise ScannerSecurityOtpInvalidError()

            if challenge.attempts >= challenge.max_attempts:
                challenge.consumed_at = now
                challenge.save(
                    update_fields=[
                        "consumed_at",
                    ],
                )
                error_to_raise = ScannerSecurityOtpMaxAttemptsError()

            else:
                candidate_hash = _hash_code(
                    code.strip(),
                )

                if not hmac.compare_digest(
                    candidate_hash,
                    challenge.code_hash,
                ):
                    challenge.attempts += 1

                    if challenge.attempts >= challenge.max_attempts:
                        challenge.consumed_at = now
                        challenge.save(
                            update_fields=[
                                "attempts",
                                "consumed_at",
                            ],
                        )
                        error_to_raise = ScannerSecurityOtpMaxAttemptsError()

                    else:
                        challenge.save(
                            update_fields=[
                                "attempts",
                            ],
                        )
                        error_to_raise = ScannerSecurityOtpInvalidError()

                else:
                    challenge.consumed_at = now
                    challenge.save(
                        update_fields=[
                            "consumed_at",
                        ],
                    )

        if error_to_raise is not None:
            raise error_to_raise
