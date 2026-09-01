"""
Récupération universelle du mot de passe FANID.

Le parcours est volontairement identique pour FAN, ORGANIZER, SCANNER et ADMIN.

Deux preuves donnent accès au même challenge à usage unique :

- lien magique signé reçu par e-mail ;
- code de secours à six chiffres.

Le code est déterministe à partir de l'identifiant aléatoire du challenge et
d'un HMAC serveur. Il peut donc être reconstruit par le worker Celery au moment
de l'envoi sans être stocké en clair ni placé dans l'Outbox.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import secrets
import uuid
from typing import Any

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.core.exceptions import ValidationBusinessError
from apps.core.outbox.publisher import publish_event

from ..constants import (
    MFA_PURPOSE_PASSWORD_RESET,
    PASSWORD_RESET_TTL_MINUTES,
    SESSION_REVOKED_PASSWORD_CHANGE,
)
from ..events import (
    AGGREGATE_USER,
    PASSWORD_RESET_COMPLETED,
    PASSWORD_RESET_REQUESTED,
    password_reset_completed_payload,
    password_reset_requested_payload,
)
from ..exceptions import OtpMaxAttemptsError, PasswordUnchangedError
from ..models import MfaChallenge, User
from .tokens import TokenService

RESET_MAGIC_SALT = "fanid.identity.password-reset.magic.v1"

RESET_CODE_SALT = "fanid.identity.password-reset.code.v1"


@dataclasses.dataclass(
    frozen=True,
    slots=True,
)
class PasswordResetRequestResult:
    created: bool


@dataclasses.dataclass(
    frozen=True,
    slots=True,
)
class PasswordResetResult:
    sessions_revoked: int


def derive_password_reset_code(
    challenge_id: uuid.UUID,
) -> str:
    """
    Recrée le code à six chiffres sans stocker le secret en clair.

    La sécurité ne repose pas sur les six chiffres seuls : cinq essais maximum,
    challenge UUID aléatoire, expiration et quotas HTTP complètent la preuve.
    """
    digest = salted_hmac(
        RESET_CODE_SALT,
        str(challenge_id),
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).digest()

    number = (
        int.from_bytes(
            digest[:8],
            "big",
        )
        % 1_000_000
    )

    return f"{number:06d}"


def _hash_code(
    code: str,
) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def build_password_reset_magic_token(
    *,
    challenge_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str:
    """
    Produit un lien signé.

    L'expiration réelle reste celle de la ligne MfaChallenge : signer plus tard
    dans le worker ne prolonge donc jamais la durée du challenge.
    """
    return signing.dumps(
        {
            "cid": str(challenge_id),
            "uid": str(user_id),
        },
        salt=RESET_MAGIC_SALT,
        compress=True,
    )


def _decode_magic_token(
    token: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    try:
        payload = signing.loads(
            token,
            salt=RESET_MAGIC_SALT,
            max_age=(int(PASSWORD_RESET_TTL_MINUTES) * 60),
        )

        challenge_id = uuid.UUID(str(payload["cid"]))

        user_id = uuid.UUID(str(payload["uid"]))
    except (
        signing.BadSignature,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise _invalid_reset_error() from exc

    return (
        challenge_id,
        user_id,
    )


def _invalid_reset_error() -> ValidationBusinessError:
    return ValidationBusinessError(
        code="PASSWORD_RESET_INVALID",
        message=("Le lien ou le code de " "réinitialisation est invalide " "ou expiré."),
    )


class PasswordResetService:
    """
    Service anonyme de récupération du mot de passe.

    Aucun rôle n'est filtré : tout compte actif FANID peut récupérer son accès.
    """

    def request(
        self,
        *,
        email: str,
    ) -> PasswordResetRequestResult:
        user = User.objects.filter(
            email=email,
        ).first()

        if user is None or not user.is_active or user.anonymized_at is not None:
            return PasswordResetRequestResult(
                created=False,
            )

        now = timezone.now()

        challenge_id = uuid.uuid4()

        code = derive_password_reset_code(challenge_id)

        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(pk=user.pk)

            if not locked_user.is_active or locked_user.anonymized_at is not None:
                return PasswordResetRequestResult(
                    created=False,
                )

            (
                MfaChallenge.objects.for_purpose(
                    locked_user,
                    MFA_PURPOSE_PASSWORD_RESET,
                )
                .filter(
                    consumed_at__isnull=True,
                )
                .update(
                    consumed_at=now,
                )
            )

            challenge = MfaChallenge.objects.create(
                id=challenge_id,
                user=locked_user,
                purpose=(MFA_PURPOSE_PASSWORD_RESET),
                code_hash=(_hash_code(code)),
                expires_at=(now + datetime.timedelta(minutes=int(PASSWORD_RESET_TTL_MINUTES))),
            )

            publish_event(
                event_type=(PASSWORD_RESET_REQUESTED),
                aggregate_type=(AGGREGATE_USER),
                aggregate_id=(locked_user.pk),
                payload=(
                    password_reset_requested_payload(
                        challenge_id=(challenge.pk),
                    )
                ),
            )

        return PasswordResetRequestResult(
            created=True,
        )

    def reset(
        self,
        *,
        new_password: str,
        token: str | None = None,
        email: str | None = None,
        code: str | None = None,
    ) -> PasswordResetResult:
        if token:
            (
                challenge_id,
                user_id,
            ) = _decode_magic_token(token)

            return self._settle(
                challenge_id=(challenge_id),
                expected_user_id=(user_id),
                provided_code=None,
                new_password=(new_password),
            )

        if not email or code is None:
            raise _invalid_reset_error()

        challenge_id = (
            MfaChallenge.objects.filter(
                user__email=email,
                purpose=(MFA_PURPOSE_PASSWORD_RESET),
            )
            .order_by("-created_at")
            .values_list(
                "pk",
                flat=True,
            )
            .first()
        )

        if challenge_id is None:
            raise _invalid_reset_error()

        return self._settle(
            challenge_id=(challenge_id),
            expected_user_id=None,
            provided_code=code,
            new_password=(new_password),
        )

    def _settle(
        self,
        *,
        challenge_id: Any,
        expected_user_id: uuid.UUID | None,
        provided_code: str | None,
        new_password: str,
    ) -> PasswordResetResult:
        outcome = "invalid"
        sessions_revoked = 0

        with transaction.atomic():
            challenge = (
                MfaChallenge.objects.select_for_update(of=("self",))
                .select_related(
                    "user",
                    "user__role",
                )
                .filter(
                    pk=challenge_id,
                    purpose=(MFA_PURPOSE_PASSWORD_RESET),
                )
                .first()
            )

            now = timezone.now()

            unusable = (
                challenge is None
                or challenge.consumed_at is not None
                or challenge.expires_at <= now
                or challenge.attempts >= challenge.max_attempts
            )

            if unusable or challenge is None:
                outcome = "invalid"
            elif expected_user_id is not None and challenge.user_id != expected_user_id:
                outcome = "invalid"
            elif provided_code is not None:
                provided_hash = _hash_code(provided_code)

                if not secrets.compare_digest(
                    challenge.code_hash,
                    provided_hash,
                ):
                    challenge.attempts += 1

                    exhausted = challenge.attempts >= challenge.max_attempts

                    if exhausted:
                        challenge.consumed_at = now

                    challenge.save(
                        update_fields=[
                            "attempts",
                            "consumed_at",
                        ]
                    )

                    outcome = "exhausted" if exhausted else "invalid"
                else:
                    sessions_revoked = self._apply_new_password(
                        challenge=(challenge),
                        new_password=(new_password),
                        now=now,
                    )

                    outcome = "ok"
            else:
                sessions_revoked = self._apply_new_password(
                    challenge=(challenge),
                    new_password=(new_password),
                    now=now,
                )

                outcome = "ok"

        if outcome == "exhausted":
            raise OtpMaxAttemptsError()

        if outcome != "ok":
            raise _invalid_reset_error()

        return PasswordResetResult(sessions_revoked=(sessions_revoked))

    @staticmethod
    def _apply_new_password(
        *,
        challenge: MfaChallenge,
        new_password: str,
        now: datetime.datetime,
    ) -> int:
        user = challenge.user

        if user.check_password(new_password):
            raise PasswordUnchangedError(
                details={"new_password": ["Le nouveau mot de passe " "doit être différent de " "l’ancien."]}
            )

        try:
            validate_password(
                new_password,
                user=user,
            )
        except DjangoValidationError as exc:
            raise ValidationBusinessError(details={"new_password": list(exc.messages)}) from exc

        user.set_password(new_password)

        user.save(
            update_fields=[
                "password",
            ]
        )

        challenge.consumed_at = now

        challenge.save(
            update_fields=[
                "consumed_at",
            ]
        )

        sessions_revoked = TokenService.revoke_all_for_user(
            user,
            SESSION_REVOKED_PASSWORD_CHANGE,
            now=now,
        )

        publish_event(
            event_type=(PASSWORD_RESET_COMPLETED),
            aggregate_type=(AGGREGATE_USER),
            aggregate_id=user.pk,
            actor_id=user.pk,
            payload=(
                password_reset_completed_payload(
                    sessions_revoked=(sessions_revoked),
                )
            ),
        )

        return sessions_revoked
