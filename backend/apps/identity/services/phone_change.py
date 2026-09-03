from __future__ import annotations

import dataclasses
import datetime
import hashlib
import logging
import re
import secrets
import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.interfaces.notifications import NotificationSender
from apps.core.outbox.publisher import publish_event

from ..constants import (
    MFA_PURPOSE_PHONE_CHANGE,
    OTP_TTL_MINUTES,
)
from ..events import (
    AGGREGATE_USER,
    USER_PHONE_CHANGED,
    USER_PROFILE_UPDATED,
    user_phone_changed_payload,
    user_profile_updated_payload,
)
from ..exceptions import (
    OtpInvalidError,
    OtpMaxAttemptsError,
)
from ..models import MfaChallenge, Session, User
from ..tokens import TokenInvalidError

logger = logging.getLogger("fanid.identity")

CODE_DIGITS = 6
PHONE_KEY_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")
PHONE_SEPARATORS_RE = re.compile(r"[\s().-]+")


def phone_key(value: Any) -> str:
    """
    Forme canonique uniquement pour comparaison/hash.

    La valeur affichee au client conserve sa mise en forme.
    """
    raw = str(value or "").strip()
    key = PHONE_SEPARATORS_RE.sub("", raw)

    if not PHONE_KEY_RE.fullmatch(key):
        raise ValueError(
            "Saisissez un numéro international valide, "
            "par exemple +33612345678."
        )

    return key


def clean_phone(value: Any) -> str:
    """
    Valide le numéro tout en conservant les séparateurs saisis.
    """
    raw = str(value or "").strip()
    phone_key(raw)
    return raw


def same_phone(
    left: Any,
    right: Any,
) -> bool:
    left_raw = str(left or "").strip()
    right_raw = str(right or "").strip()

    if left_raw == right_raw:
        return True

    if not left_raw or not right_raw:
        return False

    try:
        return phone_key(left_raw) == phone_key(right_raw)
    except ValueError:
        return False


def _hash_code(
    *,
    session_id: uuid.UUID,
    challenge_id: uuid.UUID,
    target_phone_key: str,
    code: str,
) -> str:
    raw = (
        f"{session_id}:"
        f"{challenge_id}:"
        f"{target_phone_key}:"
        f"{code}"
    )
    return hashlib.sha256(
        raw.encode("utf-8"),
    ).hexdigest()


@dataclasses.dataclass(
    frozen=True,
    slots=True,
)
class PhoneChangeRequestResult:
    challenge_id: uuid.UUID


@dataclasses.dataclass(
    frozen=True,
    slots=True,
)
class PhoneChangeConfirmResult:
    user: User
    first_record: bool
    changed: bool


class PhoneChangeService:
    """
    Remplacement de téléphone protégé par OTP.

    Le nouveau numéro n'est jamais persisté avant la
    confirmation du challenge.
    """

    def __init__(
        self,
        *,
        sender: NotificationSender,
    ) -> None:
        self._sender = sender

    def request(
        self,
        *,
        user: User,
        session_id: uuid.UUID,
        phone: str,
    ) -> PhoneChangeRequestResult:
        display_phone = clean_phone(phone)
        target_key = phone_key(display_phone)
        challenge_id = uuid.uuid4()
        code = (
            f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"
        )
        now = timezone.now()

        with transaction.atomic():
            locked_user = (
                User.objects.select_for_update()
                .get(pk=user.pk)
            )

            session = (
                Session.objects.active()
                .select_for_update()
                .filter(
                    pk=session_id,
                    user=locked_user,
                )
                .first()
            )

            if session is None:
                raise TokenInvalidError()

            invalidated = (
                MfaChallenge.objects.for_purpose(
                    locked_user,
                    MFA_PURPOSE_PHONE_CHANGE,
                )
                .filter(
                    consumed_at__isnull=True,
                )
                .update(
                    consumed_at=now,
                )
            )

            MfaChallenge.objects.create(
                id=challenge_id,
                user=locked_user,
                purpose=MFA_PURPOSE_PHONE_CHANGE,
                code_hash=_hash_code(
                    session_id=session.pk,
                    challenge_id=challenge_id,
                    target_phone_key=target_key,
                    code=code,
                ),
                expires_at=(
                    now
                    + datetime.timedelta(
                        minutes=int(
                            OTP_TTL_MINUTES,
                        )
                    )
                ),
            )

        self._send_code(
            user=locked_user,
            phone=display_phone,
            code=code,
        )

        logger.info(
            "auth.phone_change.requested",
            extra={
                "user_id": str(
                    locked_user.pk,
                ),
                "session_id": str(
                    session_id,
                ),
                "challenge_id": str(
                    challenge_id,
                ),
                "invalidated": invalidated,
            },
        )

        return PhoneChangeRequestResult(
            challenge_id=challenge_id,
        )

    def _send_code(
        self,
        *,
        user: User,
        phone: str,
        code: str,
    ) -> None:
        try:
            self._sender.send_email(
                to=user.email,
                subject=(
                    "[FANID] Validation du nouveau numéro "
                    "de téléphone"
                ),
                body=(
                    "Vous avez demandé à remplacer votre "
                    f"numéro de téléphone par {phone}.\n\n"
                    f"Votre code de validation est {code}.\n"
                    f"Il expire dans {OTP_TTL_MINUTES} minutes.\n\n"
                    "Tant que ce code n'est pas validé, "
                    "votre ancien numéro reste actif."
                ),
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "auth.phone_change.code_send_failed",
                extra={
                    "user_id": str(
                        user.pk,
                    ),
                },
            )

    def confirm(
        self,
        *,
        user: User,
        session_id: uuid.UUID,
        challenge_id: uuid.UUID,
        phone: str,
        code: str,
    ) -> PhoneChangeConfirmResult:
        display_phone = clean_phone(phone)

        outcome, result = self._settle(
            user=user,
            session_id=session_id,
            challenge_id=challenge_id,
            phone=display_phone,
            code=code,
        )

        if outcome == "exhausted":
            raise OtpMaxAttemptsError()

        if outcome != "ok" or result is None:
            raise OtpInvalidError()

        logger.info(
            "auth.phone_change.confirmed",
            extra={
                "user_id": str(
                    user.pk,
                ),
                "session_id": str(
                    session_id,
                ),
                "challenge_id": str(
                    challenge_id,
                ),
                "first_record": (
                    result.first_record
                ),
                "changed": result.changed,
            },
        )

        return result

    def _settle(
        self,
        *,
        user: User,
        session_id: uuid.UUID,
        challenge_id: uuid.UUID,
        phone: str,
        code: str,
    ) -> tuple[
        str,
        PhoneChangeConfirmResult | None,
    ]:
        now = timezone.now()
        target_key = phone_key(phone)

        with transaction.atomic():
            challenge = (
                MfaChallenge.objects
                .select_for_update(
                    of=("self",),
                )
                .filter(
                    pk=challenge_id,
                    user=user,
                    purpose=(
                        MFA_PURPOSE_PHONE_CHANGE
                    ),
                )
                .first()
            )

            if (
                challenge is None
                or challenge.consumed_at
                is not None
                or challenge.expires_at <= now
                or challenge.attempts
                >= challenge.max_attempts
            ):
                return "invalid", None

            expected_hash = _hash_code(
                session_id=session_id,
                challenge_id=challenge.pk,
                target_phone_key=target_key,
                code=code,
            )

            if not secrets.compare_digest(
                challenge.code_hash,
                expected_hash,
            ):
                challenge.attempts += 1

                exhausted = (
                    challenge.attempts
                    >= challenge.max_attempts
                )

                if exhausted:
                    challenge.consumed_at = now

                challenge.save(
                    update_fields=[
                        "attempts",
                        "consumed_at",
                    ],
                )

                return (
                    (
                        "exhausted"
                        if exhausted
                        else "invalid"
                    ),
                    None,
                )

            session = (
                Session.objects.active()
                .select_for_update()
                .filter(
                    pk=session_id,
                    user=user,
                )
                .first()
            )

            if session is None:
                challenge.consumed_at = now
                challenge.save(
                    update_fields=[
                        "consumed_at",
                    ],
                )
                return "invalid", None

            locked_user = (
                User.objects.select_for_update()
                .select_related("role")
                .get(pk=user.pk)
            )

            old_phone = str(
                locked_user.phone or "",
            ).strip()

            challenge.consumed_at = now
            challenge.save(
                update_fields=[
                    "consumed_at",
                ],
            )

            if same_phone(
                old_phone,
                phone,
            ):
                return (
                    "ok",
                    PhoneChangeConfirmResult(
                        user=locked_user,
                        first_record=False,
                        changed=False,
                    ),
                )

            first_record = not bool(
                old_phone,
            )

            locked_user.phone = phone
            locked_user.version += 1
            locked_user.updated_at = now
            locked_user.save(
                update_fields=[
                    "phone",
                    "version",
                    "updated_at",
                ],
            )

            publish_event(
                event_type=USER_PROFILE_UPDATED,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=locked_user.pk,
                actor_id=locked_user.pk,
                payload=user_profile_updated_payload(
                    changed_fields=[
                        "phone",
                    ],
                ),
            )

            publish_event(
                event_type=USER_PHONE_CHANGED,
                aggregate_type=AGGREGATE_USER,
                aggregate_id=locked_user.pk,
                actor_id=locked_user.pk,
                payload=user_phone_changed_payload(
                    first_record=first_record,
                ),
            )

            return (
                "ok",
                PhoneChangeConfirmResult(
                    user=locked_user,
                    first_record=first_record,
                    changed=True,
                ),
            )
