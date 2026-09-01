from __future__ import annotations

from typing import Any

from celery import shared_task
from django.utils import timezone

from apps.core.adapters.notifications import build_notification_sender

from .constants import SCANNER_ACTIVE, SCANNER_LEAVE_REQUESTED
from .models import Scanner


def _scanner(scanner_id: str) -> Scanner | None:
    return (
        Scanner.objects.select_related(
            "user",
            "organizer",
        )
        .filter(pk=scanner_id)
        .first()
    )


def _identity(scanner: Scanner) -> tuple[str, str, str]:
    first_name = scanner.invited_first_name or scanner.user.first_name or "Scanner"
    last_name = scanner.invited_last_name or scanner.user.last_name or ""
    email = scanner.invited_email or scanner.user.email

    return (
        first_name,
        last_name,
        email,
    )


@shared_task(
    bind=True,
    name="organizing.scanner.leave_request_emails",
    max_retries=5,
)
def send_scanner_leave_request_emails(
    self: Any,
    *,
    scanner_id: str,
) -> dict[str, Any]:
    scanner = _scanner(scanner_id)

    if scanner is None:
        return {
            "sent": False,
            "reason": "scanner_missing",
        }

    if scanner.status != SCANNER_LEAVE_REQUESTED:
        return {
            "sent": False,
            "reason": "leave_request_not_pending",
        }

    first_name, last_name, scanner_email = _identity(scanner)
    scanner_name = f"{first_name} {last_name}".strip()

    sender = build_notification_sender()

    try:
        if scanner.leave_request_scanner_email_sent_at is None:
            sender.send_email(
                to=scanner_email,
                subject="[FANID] Demande de départ envoyée",
                body=(
                    f"Bonjour {first_name},\n\n"
                    "Votre demande de suppression de votre accès scanner "
                    "a bien été transmise à l’organisateur.\n\n"
                    "Votre compte n’est pas supprimé immédiatement. "
                    "Vous recevrez un e-mail dès que l’organisateur "
                    "aura accepté ou refusé votre demande.\n\n"
                    "L’équipe FANID"
                ),
            )

            Scanner.objects.filter(
                pk=scanner.pk,
                leave_request_scanner_email_sent_at__isnull=True,
            ).update(
                leave_request_scanner_email_sent_at=timezone.now(),
            )

        scanner.refresh_from_db()

        if scanner.leave_request_organizer_email_sent_at is None:
            sender.send_email(
                to=scanner.organizer.contact_email,
                subject="[FANID] Demande de départ d’un scanner",
                body=(
                    "Bonjour,\n\n"
                    f"{scanner_name} ({scanner_email}) demande la suppression "
                    "de son accès scanner FANID.\n\n"
                    "Connectez-vous à votre espace organisateur, rubrique "
                    "Scanners, pour accepter ou refuser cette demande.\n\n"
                    "L’équipe FANID"
                ),
            )

            Scanner.objects.filter(
                pk=scanner.pk,
                leave_request_organizer_email_sent_at__isnull=True,
            ).update(
                leave_request_organizer_email_sent_at=timezone.now(),
            )

    except Exception as exc:
        retries = int(
            getattr(
                self.request,
                "retries",
                0,
            ),
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
    name="organizing.scanner.leave_rejected_emails",
    max_retries=5,
)
def send_scanner_leave_rejected_emails(
    self: Any,
    *,
    scanner_id: str,
) -> dict[str, Any]:
    scanner = _scanner(scanner_id)

    if scanner is None:
        return {
            "sent": False,
            "reason": "scanner_missing",
        }

    if scanner.status != SCANNER_ACTIVE or scanner.leave_rejected_at is None:
        return {
            "sent": False,
            "reason": "leave_request_not_rejected",
        }

    first_name, last_name, scanner_email = _identity(scanner)
    scanner_name = f"{first_name} {last_name}".strip()

    sender = build_notification_sender()

    try:
        if scanner.leave_rejected_scanner_email_sent_at is None:
            sender.send_email(
                to=scanner_email,
                subject="[FANID] Demande de départ refusée",
                body=(
                    f"Bonjour {first_name},\n\n"
                    "Votre demande de suppression de votre accès scanner "
                    "a été refusée par l’organisateur.\n\n"
                    "Votre compte scanner reste actif.\n\n"
                    "L’équipe FANID"
                ),
            )

            Scanner.objects.filter(
                pk=scanner.pk,
                leave_rejected_scanner_email_sent_at__isnull=True,
            ).update(
                leave_rejected_scanner_email_sent_at=timezone.now(),
            )

        scanner.refresh_from_db()

        if scanner.leave_rejected_organizer_email_sent_at is None:
            sender.send_email(
                to=scanner.organizer.contact_email,
                subject="[FANID] Demande de départ refusée",
                body=(
                    "Bonjour,\n\n"
                    f"Vous avez refusé la demande de départ de "
                    f"{scanner_name} ({scanner_email}).\n\n"
                    "Son accès scanner reste actif.\n\n"
                    "L’équipe FANID"
                ),
            )

            Scanner.objects.filter(
                pk=scanner.pk,
                leave_rejected_organizer_email_sent_at__isnull=True,
            ).update(
                leave_rejected_organizer_email_sent_at=timezone.now(),
            )

    except Exception as exc:
        retries = int(
            getattr(
                self.request,
                "retries",
                0,
            ),
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
