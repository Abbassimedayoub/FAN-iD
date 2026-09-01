from __future__ import annotations

import uuid
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.core.adapters.notifications import (
    build_notification_sender,
)
from apps.identity.api import (
    derive_scanner_temporary_password,
)

from .constants import (
    SCANNER_DELETED,
    SCANNER_EMAIL_SENT,
    SCANNER_INVITATION_CANCELLED,
    SCANNER_INVITED,
    SCANNER_OPENED,
)
from .models import Scanner

TERMINAL_SCANNER_STATUSES = {
    SCANNER_INVITATION_CANCELLED,
    SCANNER_DELETED,
}


def _scanner(
    scanner_id: str,
) -> Scanner | None:
    try:
        scanner_uuid = uuid.UUID(scanner_id)
    except ValueError:
        return None

    return (
        Scanner.objects.select_related(
            "user",
            "organizer",
        )
        .filter(pk=scanner_uuid)
        .first()
    )


def _revoked(
    scanner: Scanner,
) -> bool:
    return scanner.status in TERMINAL_SCANNER_STATUSES


@shared_task(
    bind=True,
    name=("organizing.scanner.invitation_emails"),
    max_retries=5,
)
def send_scanner_invitation_emails(
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

    if _revoked(scanner):
        return {
            "sent": False,
            "reason": "scanner_revoked",
        }

    temporary_password = derive_scanner_temporary_password(
        invitation_id=scanner.pk,
    )

    frontend_url = str(
        getattr(
            settings,
            "FRONTEND_URL",
            "http://localhost:5173",
        )
    ).rstrip("/")

    sender = build_notification_sender()

    try:
        if scanner.scanner_email_sent_at is None:
            sender.send_email(
                to=scanner.user.email,
                subject=("[FANID] Votre compte scanner"),
                body=(
                    f"Bonjour "
                    f"{scanner.user.first_name},\n\n"
                    "Un compte scanner FANID "
                    "vient d’être créé pour vous.\n\n"
                    f"Adresse e-mail : "
                    f"{scanner.user.email}\n"
                    f"Mot de passe temporaire : "
                    f"{temporary_password}\n\n"
                    "Ce mot de passe temporaire "
                    "est valable 5 minutes et à "
                    "usage unique. Après votre "
                    "première connexion, vous devrez "
                    "le remplacer immédiatement.\n\n"
                    f"Connexion : "
                    f"{frontend_url}/login\n\n"
                    "L’équipe FANID"
                ),
            )

            Scanner.objects.filter(
                pk=scanner.pk,
                scanner_email_sent_at__isnull=True,
            ).update(
                scanner_email_sent_at=(timezone.now()),
            )

        scanner.refresh_from_db()

        if _revoked(scanner):
            return {
                "sent": False,
                "reason": "scanner_revoked",
            }

        if scanner.organizer_email_sent_at is None:
            sender.send_email(
                to=(scanner.organizer.contact_email),
                subject=("[FANID] Invitation scanner " "envoyée"),
                body=(
                    "Bonjour,\n\n"
                    "L’invitation de "
                    f"{scanner.user.first_name} "
                    f"{scanner.user.last_name} "
                    f"({scanner.user.email}) "
                    "a été envoyée.\n\n"
                    "Pour des raisons de sécurité, "
                    "le mot de passe temporaire "
                    "n’est jamais communiqué à "
                    "l’organisateur.\n\n"
                    "L’équipe FANID"
                ),
            )

            Scanner.objects.filter(
                pk=scanner.pk,
                organizer_email_sent_at__isnull=True,
            ).update(
                organizer_email_sent_at=(timezone.now()),
            )

        scanner.refresh_from_db()

        if _revoked(scanner):
            return {
                "sent": False,
                "reason": "scanner_revoked",
            }

        if (
            scanner.status == SCANNER_INVITED
            and scanner.scanner_email_sent_at is not None
            and scanner.organizer_email_sent_at is not None
        ):
            Scanner.objects.filter(
                pk=scanner.pk,
                status=SCANNER_INVITED,
            ).update(
                status=SCANNER_EMAIL_SENT,
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
    name=("organizing.scanner.milestone_emails"),
    max_retries=5,
)
def send_scanner_milestone_emails(
    self: Any,
    *,
    scanner_id: str,
    milestone: str,
) -> dict[str, Any]:
    scanner = _scanner(scanner_id)

    if scanner is None:
        return {
            "sent": False,
            "reason": "scanner_missing",
        }

    if _revoked(scanner):
        return {
            "sent": False,
            "reason": "scanner_revoked",
        }

    sender = build_notification_sender()

    if milestone == "OPENED":
        scanner_field = "opened_scanner_email_sent_at"
        organizer_field = "opened_organizer_email_sent_at"

        scanner_subject = "[FANID] Première connexion scanner"

        scanner_message = (
            "Votre compte scanner a été ouvert "
            "pour la première fois. Vous devez "
            "maintenant remplacer votre mot de "
            "passe temporaire."
        )

        organizer_subject = "[FANID] Scanner : compte ouvert"

        organizer_message = (
            f"{scanner.user.first_name} "
            f"{scanner.user.last_name} "
            f"({scanner.user.email}) vient "
            "d’ouvrir son compte scanner."
        )

    elif milestone == "ACTIVE":
        scanner_field = "active_scanner_email_sent_at"
        organizer_field = "active_organizer_email_sent_at"

        scanner_subject = "[FANID] Votre compte scanner " "est actif"

        scanner_message = (
            "Votre mot de passe temporaire a " "été remplacé. Votre compte scanner " "est maintenant actif."
        )

        organizer_subject = "[FANID] Scanner : compte actif"

        organizer_message = (
            f"{scanner.user.first_name} "
            f"{scanner.user.last_name} "
            f"({scanner.user.email}) a terminé "
            "l’activation de son compte."
        )

    else:
        return {
            "sent": False,
            "reason": "unknown_milestone",
        }

    try:
        scanner.refresh_from_db()

        if _revoked(scanner):
            return {
                "sent": False,
                "reason": "scanner_revoked",
            }

        if (
            getattr(
                scanner,
                scanner_field,
            )
            is None
        ):
            sender.send_email(
                to=scanner.user.email,
                subject=scanner_subject,
                body=(
                    f"Bonjour "
                    f"{scanner.user.first_name},"
                    "\n\n"
                    f"{scanner_message}"
                    "\n\n"
                    "L’équipe FANID"
                ),
            )

            Scanner.objects.filter(
                pk=scanner.pk,
                **{
                    f"{scanner_field}__isnull": (True),
                },
            ).update(
                **{
                    scanner_field: (timezone.now()),
                },
            )

        scanner.refresh_from_db()

        if _revoked(scanner):
            return {
                "sent": False,
                "reason": "scanner_revoked",
            }

        if (
            getattr(
                scanner,
                organizer_field,
            )
            is None
        ):
            sender.send_email(
                to=(scanner.organizer.contact_email),
                subject=organizer_subject,
                body=("Bonjour,\n\n" f"{organizer_message}" "\n\n" "L’équipe FANID"),
            )

            Scanner.objects.filter(
                pk=scanner.pk,
                **{
                    f"{organizer_field}__isnull": (True),
                },
            ).update(
                **{
                    organizer_field: (timezone.now()),
                },
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
    name=("organizing.scanner.revocation_emails"),
    max_retries=5,
)
def send_scanner_revocation_emails(
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

    if scanner.status not in (TERMINAL_SCANNER_STATUSES):
        return {
            "sent": False,
            "reason": "scanner_not_revoked",
        }

    scanner_email = scanner.invited_email

    if not scanner_email:
        return {
            "sent": False,
            "reason": "scanner_email_missing",
        }

    first_name = scanner.invited_first_name or "Scanner"

    last_name = scanner.invited_last_name or ""

    if scanner.status == SCANNER_INVITATION_CANCELLED:
        scanner_subject = "[FANID] Invitation scanner annulée"

        scanner_message = (
            "Votre invitation à utiliser FANID " "comme scanner a été annulée par " "l’organisateur."
        )

        organizer_subject = "[FANID] Invitation scanner annulée"

        organizer_message = (
            f"L’invitation de {first_name} " f"{last_name} ({scanner_email}) " "a été annulée."
        )

    else:
        scanner_subject = "[FANID] Accès scanner retiré"

        scanner_message = (
            "Votre accès scanner FANID a été "
            "retiré. Toutes vos sessions ont été "
            "révoquées."
        )

        organizer_subject = "[FANID] Scanner retiré"

        organizer_message = (
            f"L’accès scanner de {first_name} "
            f"{last_name} ({scanner_email}) "
            "a été retiré et ses sessions ont "
            "été révoquées."
        )

    sender = build_notification_sender()

    try:
        if scanner.revocation_scanner_email_sent_at is None:
            sender.send_email(
                to=scanner_email,
                subject=scanner_subject,
                body=(f"Bonjour {first_name},\n\n" f"{scanner_message}\n\n" "L’équipe FANID"),
            )

            Scanner.objects.filter(
                pk=scanner.pk,
                revocation_scanner_email_sent_at__isnull=True,
            ).update(
                revocation_scanner_email_sent_at=(timezone.now()),
            )

        scanner.refresh_from_db()

        if scanner.revocation_organizer_email_sent_at is None:
            sender.send_email(
                to=(scanner.organizer.contact_email),
                subject=organizer_subject,
                body=("Bonjour,\n\n" f"{organizer_message}\n\n" "L’équipe FANID"),
            )

            Scanner.objects.filter(
                pk=scanner.pk,
                revocation_organizer_email_sent_at__isnull=True,
            ).update(
                revocation_organizer_email_sent_at=(timezone.now()),
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
    name=("organizing.scanner." "invitation_reissued_emails"),
    max_retries=5,
)
def send_scanner_invitation_reissued_emails(
    self: Any,
    *,
    scanner_id: str,
    generation: int,
) -> dict[str, Any]:
    scanner = _scanner(scanner_id)

    if scanner is None:
        return {
            "sent": False,
            "reason": "scanner_missing",
        }

    if _revoked(scanner):
        return {
            "sent": False,
            "reason": "scanner_revoked",
        }

    if scanner.status not in {
        SCANNER_INVITED,
        SCANNER_EMAIL_SENT,
        SCANNER_OPENED,
    }:
        return {
            "sent": False,
            "reason": "scanner_not_pre_active",
        }

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

    scanner_email = scanner.invited_email or scanner.user.email

    first_name = scanner.invited_first_name or scanner.user.first_name

    last_name = scanner.invited_last_name or scanner.user.last_name

    scanner_name = f"{first_name} {last_name}".strip()

    frontend_url = str(
        getattr(
            settings,
            "FRONTEND_URL",
            "http://localhost:5173",
        )
    ).rstrip("/")

    sender = build_notification_sender()

    try:
        sender.send_email(
            to=scanner_email,
            subject=("[FANID] Nouvelle invitation scanner"),
            body=(
                f"Bonjour {first_name},\n\n"
                "Votre invitation scanner FANID "
                "vient d'être renouvelée.\n\n"
                f"Adresse e-mail : "
                f"{scanner_email}\n"
                "Nouveau mot de passe "
                "temporaire : "
                f"{temporary_password}\n\n"
                "Ce mot de passe remplace "
                "immédiatement tous les anciens "
                "mots de passe temporaires et "
                "reste valable 5 minutes.\n\n"
                "Après votre connexion, vous "
                "devrez choisir votre mot de "
                "passe personnel dans "
                "l'application mobile FANID.\n\n"
                f"Connexion : "
                f"{frontend_url}/login\n\n"
                "L'équipe FANID"
            ),
        )

        sender.send_email(
            to=(scanner.organizer.contact_email),
            subject=("[FANID] Invitation scanner renvoyée"),
            body=(
                "Bonjour,\n\n"
                "Une nouvelle invitation a été "
                f"envoyée à {scanner_name} "
                f"({scanner_email}).\n\n"
                "Un nouveau mot de passe "
                "temporaire valable 5 minutes "
                "a été généré.\n\n"
                "Pour des raisons de sécurité, "
                "ce mot de passe n'est jamais "
                "communiqué à l'organisateur.\n\n"
                "L'équipe FANID"
            ),
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
