from __future__ import annotations

import uuid
from typing import Any

from celery import shared_task
from django.utils import timezone

from apps.catalog.api import (
    get_event_notification_summary,
    list_active_scanner_ids_for_event,
)
from apps.catalog.events import (
    CATALOG_EVENT_CANCELLED,
    CATALOG_EVENT_POSTPONED,
    CATALOG_EVENT_SUSPENDED,
)
from apps.core.adapters.notifications import (
    build_notification_sender,
)
from apps.organizing.api import (
    get_organizer_notification_summary,
    get_scanner_assignment_summary,
    list_scanner_assignment_summaries,
)

LIFECYCLE_LABELS = {
    CATALOG_EVENT_POSTPONED: "reporté",
    CATALOG_EVENT_SUSPENDED: "suspendu",
    CATALOG_EVENT_CANCELLED: "annulé",
}


def _event_details(
    event: Any,
) -> str:
    starts_at = timezone.localtime(
        event.starts_at,
    )

    lines = [
        f"Événement : {event.name}",
        ("Date : " + starts_at.strftime("%d/%m/%Y à %H:%M")),
        f"Lieu : {event.venue or 'Non renseigné'}",
        f"Statut : {event.status}",
    ]

    if event.lifecycle_reason:
        lines.append(f"Motif : {event.lifecycle_reason}")

    return "\n".join(lines)


def _retry(
    task: Any,
    exc: Exception,
) -> None:
    retries = int(
        getattr(
            task.request,
            "retries",
            0,
        )
    )

    raise task.retry(
        exc=exc,
        countdown=min(
            30 * (2**retries),
            600,
        ),
    ) from exc


@shared_task(
    bind=True,
    name=("notifying.event_scanner." "assignment_emails"),
    max_retries=5,
)
def send_event_scanner_assignment_emails(
    self: Any,
    *,
    event_id: str,
    scanner_id: str,
    change: str,
) -> dict[str, Any]:
    try:
        event_uuid = uuid.UUID(event_id)
        scanner_uuid = uuid.UUID(scanner_id)
    except ValueError:
        return {
            "sent": False,
            "reason": "invalid_identifier",
        }

    event = get_event_notification_summary(
        event_id=event_uuid,
    )

    if event is None or event.organizer_id is None:
        return {
            "sent": False,
            "reason": "event_missing",
        }

    scanner = get_scanner_assignment_summary(
        organizer_id=event.organizer_id,
        scanner_id=scanner_uuid,
        assignable_only=False,
    )

    organizer = get_organizer_notification_summary(
        organizer_id=event.organizer_id,
    )

    if scanner is None:
        return {
            "sent": False,
            "reason": "scanner_missing",
        }

    if organizer is None:
        return {
            "sent": False,
            "reason": "organizer_missing",
        }

    scanner_name = (f"{scanner.first_name} " f"{scanner.last_name}").strip()

    details = _event_details(event)

    if change == "ASSIGNED":
        scanner_subject = "[FANID] Nouvel événement affecté : " f"{event.name}"
        scanner_action = "Vous venez d’être affecté à cet " "événement."
        organizer_subject = "[FANID] Trace affectation scanner : " f"{event.name}"
        organizer_action = f"{scanner_name} ({scanner.email}) " "a été affecté à cet événement."
    elif change == "UNASSIGNED":
        scanner_subject = "[FANID] Retrait d’une affectation : " f"{event.name}"
        scanner_action = "Vous avez été retiré de " "l’affectation à cet événement."
        organizer_subject = "[FANID] Trace retrait scanner : " f"{event.name}"
        organizer_action = f"{scanner_name} ({scanner.email}) " "a été retiré de cet événement."
    else:
        return {
            "sent": False,
            "reason": "unsupported_change",
        }

    scanner_body = (
        f"Bonjour {scanner.first_name},\n\n"
        f"{scanner_action}\n\n"
        f"{details}\n\n"
        "Votre portail FANID affiche uniquement "
        "les événements qui vous sont actuellement "
        "affectés.\n\n"
        "L’équipe FANID"
    )

    organizer_body = (
        "Bonjour,\n\n"
        "Voici votre trace d’affectation scanner.\n\n"
        f"{organizer_action}\n\n"
        f"{details}\n\n"
        "L’équipe FANID"
    )

    sender = build_notification_sender()

    try:
        sender.send_email(
            to=scanner.email,
            subject=scanner_subject,
            body=scanner_body,
        )

        sender.send_email(
            to=organizer.contact_email,
            subject=organizer_subject,
            body=organizer_body,
        )
    except Exception as exc:
        _retry(
            self,
            exc,
        )

    return {
        "sent": True,
        "recipients": 2,
        "change": change,
    }


@shared_task(
    bind=True,
    name=("notifying.event_scanner." "lifecycle_emails"),
    max_retries=5,
)
def send_event_scanner_lifecycle_emails(
    self: Any,
    *,
    event_id: str,
    change: str,
) -> dict[str, Any]:
    label = LIFECYCLE_LABELS.get(change)

    if label is None:
        return {
            "sent": False,
            "reason": "unsupported_change",
        }

    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        return {
            "sent": False,
            "reason": "invalid_identifier",
        }

    event = get_event_notification_summary(
        event_id=event_uuid,
    )

    if event is None or event.organizer_id is None:
        return {
            "sent": False,
            "reason": "event_missing",
        }

    scanner_ids = list(
        list_active_scanner_ids_for_event(
            event_id=event_uuid,
        )
    )

    scanners = list_scanner_assignment_summaries(
        organizer_id=event.organizer_id,
        scanner_ids=scanner_ids,
    )

    organizer = get_organizer_notification_summary(
        organizer_id=event.organizer_id,
    )

    if organizer is None:
        return {
            "sent": False,
            "reason": "organizer_missing",
        }

    details = _event_details(event)
    sender = build_notification_sender()
    sent = 0

    try:
        for scanner in scanners:
            sender.send_email(
                to=scanner.email,
                subject=(f"[FANID] Événement {label} : " f"{event.name}"),
                body=(
                    f"Bonjour {scanner.first_name},\n\n"
                    "Un événement qui vous est affecté "
                    f"a été {label}.\n\n"
                    f"{details}\n\n"
                    "Consultez votre portail FANID "
                    "pour voir son état à jour.\n\n"
                    "L’équipe FANID"
                ),
            )

            sent += 1

        sender.send_email(
            to=organizer.contact_email,
            subject=(f"[FANID] Trace événement {label} : " f"{event.name}"),
            body=(
                "Bonjour,\n\n"
                "Voici votre trace de changement "
                "d’événement.\n\n"
                f"{details}\n\n"
                f"{len(scanners)} scanner"
                f"{'s' if len(scanners) != 1 else ''} "
                "actuellement affecté"
                f"{'s' if len(scanners) != 1 else ''} "
                "a/ont été inclus dans la notification.\n\n"
                "L’équipe FANID"
            ),
        )

        sent += 1
    except Exception as exc:
        _retry(
            self,
            exc,
        )

    return {
        "sent": True,
        "recipients": sent,
        "scanner_recipients": len(scanners),
        "change": change,
    }
