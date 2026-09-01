from __future__ import annotations

import uuid
from typing import Any

from celery import shared_task
from django.utils import timezone

from apps.core.adapters.notifications import build_notification_sender

from .models import ScannerRevocationChallenge
from .scanner_security import (
    SCANNER_SECURITY_ACTION_LEAVE_ACCEPT,
    SCANNER_SECURITY_ACTION_LEAVE_REQUEST,
    derive_scanner_security_code,
)


@shared_task(
    bind=True,
    name="organizing.scanner.security_code_email",
    max_retries=5,
)
def send_scanner_security_code_email(
    self: Any,
    *,
    challenge_id: str,
) -> dict[str, Any]:
    try:
        challenge_uuid = uuid.UUID(
            challenge_id,
        )
    except ValueError:
        return {
            "sent": False,
            "reason": "invalid_challenge_id",
        }

    challenge = (
        ScannerRevocationChallenge.objects.select_related(
            "requested_by",
            "scanner",
        )
        .filter(
            pk=challenge_uuid,
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )

    if challenge is None:
        return {
            "sent": False,
            "reason": "challenge_unavailable",
        }

    code = derive_scanner_security_code(
        challenge.pk,
    )

    if challenge.action == SCANNER_SECURITY_ACTION_LEAVE_REQUEST:
        action_text = "confirmer votre demande de suppression " "de votre accès scanner"
        subject = "[FANID] Code de confirmation " "de votre demande scanner"
    elif challenge.action == SCANNER_SECURITY_ACTION_LEAVE_ACCEPT:
        action_text = "accepter la demande de départ " "et retirer ce scanner"
        subject = "[FANID] Code de sécurité " "pour le retrait d’un scanner"
    else:
        action_text = "annuler l’invitation ou retirer ce scanner"
        subject = "[FANID] Code de sécurité " "pour le retrait d’un scanner"

    first_name = challenge.requested_by.first_name.strip()

    greeting = f"Bonjour {first_name}," if first_name else "Bonjour,"

    body = (
        f"{greeting}\n\n"
        "Vous avez demandé une confirmation de sécurité "
        f"pour {action_text}.\n\n"
        "Votre code de vérification FANID est :\n\n"
        f"{code}\n\n"
        "Ce code expire dans 5 minutes et ne peut être "
        "utilisé qu’une seule fois.\n\n"
        "Si vous n’êtes pas à l’origine de cette demande, "
        "ne communiquez pas ce code et ignorez ce message.\n\n"
        "L’équipe FANID"
    )

    try:
        build_notification_sender().send_email(
            to=challenge.requested_by.email,
            subject=subject,
            body=body,
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

        raise self.retry(
            exc=exc,
            countdown=countdown,
        )

    return {
        "sent": True,
    }
