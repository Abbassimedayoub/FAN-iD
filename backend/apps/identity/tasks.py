from __future__ import annotations

import logging
import uuid
from typing import Any
from urllib.parse import urlencode

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.core.adapters.notifications import build_notification_sender

from .constants import MFA_PURPOSE_PASSWORD_RESET, PASSWORD_RESET_TTL_MINUTES
from .models import MfaChallenge, User
from .services.password_reset import build_password_reset_magic_token, derive_password_reset_code

logger = logging.getLogger("fanid.identity")


def _password_reset_user_and_challenge(
    *,
    user_id: str,
    challenge_id: str,
) -> tuple[User | None, MfaChallenge | None]:
    try:
        user_uuid = uuid.UUID(user_id)

        challenge_uuid = uuid.UUID(challenge_id)
    except ValueError:
        return None, None

    user = User.objects.filter(
        pk=user_uuid,
        is_active=True,
        anonymized_at__isnull=True,
    ).first()

    if user is None:
        return None, None

    challenge = MfaChallenge.objects.filter(
        pk=challenge_uuid,
        user_id=user_uuid,
        purpose=(MFA_PURPOSE_PASSWORD_RESET),
        consumed_at__isnull=True,
        expires_at__gt=(timezone.now()),
    ).first()

    return user, challenge


@shared_task(
    bind=True,
    name="identity.password_reset_email",
    max_retries=5,
)
def send_password_reset_email(
    self: Any,
    *,
    user_id: str,
    challenge_id: str,
) -> dict[str, Any]:
    user, challenge = _password_reset_user_and_challenge(
        user_id=user_id,
        challenge_id=challenge_id,
    )

    if user is None or challenge is None:
        return {
            "sent": False,
            "reason": ("challenge_unavailable"),
        }

    code = derive_password_reset_code(challenge.pk)

    token = build_password_reset_magic_token(
        challenge_id=(challenge.pk),
        user_id=user.pk,
    )

    frontend_url = str(
        getattr(
            settings,
            "FRONTEND_URL",
            "http://localhost:5173",
        )
    ).rstrip("/")

    reset_url = (
        frontend_url
        + "/password-reset?"
        + urlencode(
            {
                "token": token,
            }
        )
    )

    first_name = user.first_name.strip()

    greeting = f"Bonjour {first_name}," if first_name else "Bonjour,"

    subject = "[FANID] Réinitialisation " "de votre mot de passe"

    body = (
        f"{greeting}\n\n"
        "Une demande de réinitialisation du mot de passe "
        "de votre compte FANID a été reçue.\n\n"
        "Méthode la plus simple : ouvrez ce lien sécurisé :\n"
        f"{reset_url}\n\n"
        "Code de secours si vous préférez le saisir manuellement :\n"
        f"{code}\n\n"
        f"Le lien et le code expirent dans "
        f"{PASSWORD_RESET_TTL_MINUTES} minutes et ne peuvent être "
        "utilisés qu’une seule fois.\n\n"
        "Si vous n’êtes pas à l’origine de cette demande, "
        "ignorez simplement ce message.\n\n"
        "L’équipe FANID"
    )

    try:
        (
            build_notification_sender().send_email(
                to=user.email,
                subject=subject,
                body=body,
            )
        )
    except Exception as exc:
        retries = int(
            getattr(
                self.request,
                "retries",
                0,
            )
        )

        countdown = min(
            30 * (2**retries),
            600,
        )

        logger.warning(
            "identity.password_reset.email_retry",
            extra={
                "user_id": user_id,
                "retry_in_seconds": (countdown),
            },
        )

        raise self.retry(
            exc=exc,
            countdown=countdown,
        ) from exc

    logger.info(
        "identity.password_reset.email_sent",
        extra={
            "user_id": user_id,
        },
    )

    return {
        "sent": True,
    }


@shared_task(
    bind=True,
    name="identity.password_changed_email",
    max_retries=5,
)
def send_password_changed_email(
    self: Any,
    *,
    user_id: str,
) -> dict[str, Any]:
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return {
            "sent": False,
            "reason": "invalid_user",
        }

    user = User.objects.filter(
        pk=user_uuid,
        is_active=True,
        anonymized_at__isnull=True,
    ).first()

    if user is None:
        return {
            "sent": False,
            "reason": "user_missing",
        }

    first_name = user.first_name.strip()

    greeting = f"Bonjour {first_name}," if first_name else "Bonjour,"

    subject = "[FANID] Votre mot de passe " "a été modifié"

    body = (
        f"{greeting}\n\n"
        "Le mot de passe de votre compte FANID vient d’être "
        "réinitialisé avec succès.\n\n"
        "Toutes les sessions précédemment ouvertes ont été "
        "déconnectées par sécurité.\n\n"
        "Si vous n’êtes pas à l’origine de cette modification, "
        "contactez immédiatement l’équipe FANID.\n\n"
        "L’équipe FANID"
    )

    try:
        (
            build_notification_sender().send_email(
                to=user.email,
                subject=subject,
                body=body,
            )
        )
    except Exception as exc:
        retries = int(
            getattr(
                self.request,
                "retries",
                0,
            )
        )

        countdown = min(
            30 * (2**retries),
            600,
        )

        logger.warning(
            "identity.password_changed.email_retry",
            extra={
                "user_id": user_id,
                "retry_in_seconds": (countdown),
            },
        )

        raise self.retry(
            exc=exc,
            countdown=countdown,
        ) from exc

    logger.info(
        "identity.password_changed.email_sent",
        extra={
            "user_id": user_id,
        },
    )

    return {
        "sent": True,
    }

@shared_task(
    name="identity.send_phone_changed_email",
)
def send_phone_changed_email(
    *,
    user_id: str,
    first_record: bool,
) -> None:
    import logging

    task_logger = logging.getLogger(
        "fanid.identity",
    )

    user = User.objects.filter(
        pk=user_id,
    ).first()

    if user is None:
        return

    phone = str(
        user.phone or "",
    ).strip()

    if not phone:
        return

    if first_record:
        subject = (
            "[FANID] Numéro de téléphone enregistré"
        )
        body = (
            "Votre numéro de téléphone a été enregistré : "
            f"{phone}."
        )
    else:
        subject = (
            "[FANID] Numéro de téléphone modifié"
        )
        body = (
            "Votre numéro de téléphone est désormais "
            f"{phone}. "
            "Si vous n'êtes pas à l'origine de cette "
            "modification, contactez immédiatement FANID."
        )

    try:
        build_notification_sender().send_email(
            to=user.email,
            subject=subject,
            body=body,
        )
    except Exception:  # noqa: BLE001
        task_logger.exception(
            "auth.phone_change.confirmation_email_failed",
            extra={
                "user_id": str(
                    user.pk,
                ),
            },
        )
