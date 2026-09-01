from __future__ import annotations

import uuid
from typing import Any

from celery import shared_task
from django.utils import timezone

from apps.core.adapters.notifications import (
    build_notification_sender,
)
from apps.identity.api import (
    derive_scanner_temporary_password,
)

from .constants import (
    SCANNER_CREDENTIAL_REQUEST_FULFILLED,
    SCANNER_DELETED,
    SCANNER_INVITATION_CANCELLED,
)
from .models import ScannerCredentialRequest


def _request(
    request_id: str,
) -> ScannerCredentialRequest | None:
    try:
        value = uuid.UUID(request_id)
    except ValueError:
        return None

    return (
        ScannerCredentialRequest.objects.select_related(
            "scanner",
            "scanner__user",
            "scanner__organizer",
        )
        .filter(pk=value)
        .first()
    )


def _terminal(
    request: ScannerCredentialRequest,
) -> bool:
    return request.scanner.status in {
        SCANNER_INVITATION_CANCELLED,
        SCANNER_DELETED,
    }


def _scanner_email(
    request: ScannerCredentialRequest,
) -> str:
    return request.scanner.invited_email or request.scanner.user.email


def _scanner_name(
    request: ScannerCredentialRequest,
) -> str:
    scanner = request.scanner

    first_name = scanner.invited_first_name or scanner.user.first_name

    last_name = scanner.invited_last_name or scanner.user.last_name

    return f"{first_name} {last_name}".strip()


@shared_task(
    bind=True,
    name=("organizing.scanner." "password_help_emails"),
    max_retries=5,
)
def send_scanner_password_help_emails(
    self: Any,
    *,
    request_id: str,
) -> dict[str, Any]:
    request = _request(request_id)

    if request is None:
        return {
            "sent": False,
            "reason": "request_missing",
        }

    if _terminal(request):
        return {
            "sent": False,
            "reason": "scanner_revoked",
        }

    scanner = request.scanner
    email = _scanner_email(request)
    name = _scanner_name(request)

    sender = build_notification_sender()

    try:
        if request.request_scanner_email_sent_at is None:
            sender.send_email(
                to=email,
                subject=("[FANID] Demande de " "nouvel accès reçue"),
                body=(
                    f"Bonjour {name},\n\n"
                    "Votre demande de nouveau "
                    "mot de passe scanner a bien "
                    "été transmise à votre "
                    "organisateur.\n\n"
                    "Après validation, vous "
                    "recevrez un nouveau mot de "
                    "passe temporaire valable "
                    "5 minutes.\n\n"
                    "L'équipe FANID"
                ),
            )

            (
                ScannerCredentialRequest.objects.filter(
                    pk=request.pk,
                    request_scanner_email_sent_at__isnull=True,
                ).update(
                    request_scanner_email_sent_at=(timezone.now()),
                )
            )

        request.refresh_from_db()

        if request.request_organizer_email_sent_at is None:
            sender.send_email(
                to=(scanner.organizer.contact_email),
                subject=("[FANID] Demande de nouveau " "mot de passe scanner"),
                body=(
                    "Bonjour,\n\n"
                    f"{name} ({email}) demande "
                    "un nouveau mot de passe "
                    "scanner.\n\n"
                    "Vous pouvez traiter la "
                    "demande depuis votre espace "
                    "Scanners FANID.\n\n"
                    "Le mot de passe ne vous "
                    "sera jamais communiqué.\n\n"
                    "L'équipe FANID"
                ),
            )

            (
                ScannerCredentialRequest.objects.filter(
                    pk=request.pk,
                    request_organizer_email_sent_at__isnull=True,
                ).update(
                    request_organizer_email_sent_at=(timezone.now()),
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

        raise self.retry(
            exc=exc,
            countdown=min(
                30 * (2**retries),
                600,
            ),
        ) from exc

    return {
        "sent": True,
    }


@shared_task(
    bind=True,
    name=("organizing.scanner." "password_reissued_emails"),
    max_retries=5,
)
def send_scanner_password_reissued_emails(
    self: Any,
    *,
    request_id: str,
    generation: int,
) -> dict[str, Any]:
    request = _request(request_id)

    if request is None:
        return {
            "sent": False,
            "reason": "request_missing",
        }

    if _terminal(request):
        return {
            "sent": False,
            "reason": "scanner_revoked",
        }

    if request.status != SCANNER_CREDENTIAL_REQUEST_FULFILLED:
        return {
            "sent": False,
            "reason": "request_not_fulfilled",
        }

    scanner = request.scanner

    scanner.user.refresh_from_db()

    if scanner.user.temporary_password_generation != generation:
        return {
            "sent": False,
            "reason": "generation_obsolete",
        }

    expires_at = scanner.user.temporary_password_expires_at

    if expires_at is None or expires_at <= timezone.now():
        return {
            "sent": False,
            "reason": ("temporary_password_expired"),
        }

    temporary_password = derive_scanner_temporary_password(
        invitation_id=scanner.pk,
        generation=generation,
    )

    email = _scanner_email(request)
    name = _scanner_name(request)

    sender = build_notification_sender()

    try:
        if request.reissue_scanner_email_sent_at is None:
            sender.send_email(
                to=email,
                subject=("[FANID] Nouveau mot de " "passe scanner"),
                body=(
                    f"Bonjour {name},\n\n"
                    "Votre organisateur a "
                    "accepté votre demande.\n\n"
                    "Votre nouveau mot de passe "
                    "temporaire est :\n\n"
                    f"{temporary_password}\n\n"
                    "Il est valable 5 minutes. "
                    "Tous les anciens mots de "
                    "passe temporaires sont "
                    "désormais invalides.\n\n"
                    "Après connexion, vous devrez "
                    "choisir votre mot de passe "
                    "personnel dans l'application "
                    "mobile FANID.\n\n"
                    "L'équipe FANID"
                ),
            )

            (
                ScannerCredentialRequest.objects.filter(
                    pk=request.pk,
                    reissue_scanner_email_sent_at__isnull=True,
                ).update(
                    reissue_scanner_email_sent_at=(timezone.now()),
                )
            )

        request.refresh_from_db()

        if request.reissue_organizer_email_sent_at is None:
            sender.send_email(
                to=(scanner.organizer.contact_email),
                subject=("[FANID] Nouvel accès " "scanner envoyé"),
                body=(
                    "Bonjour,\n\n"
                    "Un nouveau mot de passe "
                    "temporaire valable 5 minutes "
                    f"a été envoyé à {name} "
                    f"({email}).\n\n"
                    "Pour des raisons de sécurité, "
                    "ce mot de passe n'est jamais "
                    "affiché dans votre espace "
                    "organisateur.\n\n"
                    "L'équipe FANID"
                ),
            )

            (
                ScannerCredentialRequest.objects.filter(
                    pk=request.pk,
                    reissue_organizer_email_sent_at__isnull=True,
                ).update(
                    reissue_organizer_email_sent_at=(timezone.now()),
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

        raise self.retry(
            exc=exc,
            countdown=min(
                30 * (2**retries),
                600,
            ),
        ) from exc

    return {
        "sent": True,
    }
