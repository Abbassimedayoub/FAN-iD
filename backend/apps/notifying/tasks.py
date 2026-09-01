from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from apps.core.adapters.notifications import build_notification_sender
from apps.organizing.constants import ORGANIZER_APPROVED, ORGANIZER_REJECTED, ORGANIZER_SUSPENDED
from apps.organizing.models import Organizer

logger = logging.getLogger("fanid.notifying")


def organizer_decision_email(
    *,
    organizer: Organizer,
    decision: str,
) -> tuple[str, str]:
    first_name = organizer.user.first_name.strip() or "Bonjour"

    if decision == ORGANIZER_APPROVED:
        subject = "[FANID] Votre demande organisateur " "est approuvée"

        body = (
            f"Bonjour {first_name},\n\n"
            f"Bonne nouvelle : la demande de "
            f"l’organisation « {organizer.org_name} » "
            "a été approuvée par l’équipe FANID.\n\n"
            "Votre espace organisateur est maintenant "
            "validé. Vous pouvez vous connecter à FANID "
            "pour accéder aux fonctionnalités réservées "
            "aux organisateurs approuvés.\n\n"
            "Cordialement,\n"
            "L’équipe FANID"
        )

        return subject, body

    if decision == ORGANIZER_REJECTED:
        subject = "[FANID] Décision concernant votre " "demande organisateur"

        reason = organizer.rejection_reason or "Aucun motif complémentaire n’a été fourni."

        body = (
            f"Bonjour {first_name},\n\n"
            f"La demande de l’organisation "
            f"« {organizer.org_name} » n’a pas été "
            "approuvée.\n\n"
            f"Motif : {reason}\n\n"
            "Si vous avez besoin d’informations "
            "complémentaires, vous pouvez contacter "
            "l’équipe FANID.\n\n"
            "Cordialement,\n"
            "L’équipe FANID"
        )

        return subject, body

    if decision == ORGANIZER_SUSPENDED:
        subject = "[FANID] Votre compte organisateur " "a été suspendu"

        body = (
            f"Bonjour {first_name},\n\n"
            f"Le compte organisateur de l’organisation "
            f"« {organizer.org_name} » a été suspendu "
            "par l’équipe FANID.\n\n"
            "Les fonctionnalités réservées aux "
            "organisateurs approuvés ne sont plus "
            "accessibles pour le moment.\n\n"
            "Si vous pensez qu’il s’agit d’une erreur "
            "ou si vous souhaitez obtenir davantage "
            "d’informations, contactez l’équipe FANID.\n\n"
            "Cordialement,\n"
            "L’équipe FANID"
        )

        return subject, body

    raise ValueError(f"Décision organisateur non supportée : {decision!r}")


@shared_task(
    bind=True,
    name="notifying.organizer_decision_email",
    max_retries=5,
)
def send_organizer_decision_email(
    self: Any,
    *,
    organizer_id: str,
    decision: str,
) -> dict[str, Any]:
    """
    Envoie le résultat de validation hors transaction Outbox.

    Les erreurs réseau SMTP sont rejouées par Celery avec un backoff.
    """

    try:
        organizer = Organizer.objects.select_related("user").get(pk=organizer_id)
    except Organizer.DoesNotExist:
        logger.warning(
            "notifying.organizer.missing",
            extra={"organizer_id": organizer_id},
        )
        return {
            "sent": False,
            "reason": "organizer_missing",
        }

    subject, body = organizer_decision_email(
        organizer=organizer,
        decision=decision,
    )

    try:
        build_notification_sender().send_email(
            to=organizer.user.email,
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

        logger.warning(
            "notifying.organizer.email_retry",
            extra={
                "organizer_id": organizer_id,
                "decision": decision,
                "retry_in_seconds": countdown,
            },
        )

        raise self.retry(
            exc=exc,
            countdown=countdown,
        ) from exc

    logger.info(
        "notifying.organizer.email_sent",
        extra={
            "organizer_id": organizer_id,
            "decision": decision,
        },
    )

    return {
        "sent": True,
        "decision": decision,
    }
