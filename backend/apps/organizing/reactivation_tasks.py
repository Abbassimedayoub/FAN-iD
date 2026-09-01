from __future__ import annotations

import uuid
from typing import Any, Iterable

from celery import shared_task
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone

from apps.core.adapters.notifications import (
    build_notification_sender,
)

from .models import OrganizerReactivationRequest


def _unique_emails(
    values: Iterable[str | None],
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        email = (value or "").strip()

        if not email:
            continue

        key = email.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(email)

    return result


def _admin_emails() -> list[str]:
    User = get_user_model()

    users = (
        User.objects.filter(
            role__name="ADMIN",
            is_active=True,
            anonymized_at__isnull=True,
        )
        .exclude(email="")
        .order_by("email")
    )

    return _unique_emails(user.email for user in users)


def _load_request(
    request_id: str,
) -> OrganizerReactivationRequest | None:
    try:
        request_uuid = uuid.UUID(request_id)
    except ValueError:
        return None

    return (
        OrganizerReactivationRequest.objects.select_related(
            "organizer",
            "organizer__user",
            "requested_by",
            "reviewed_by",
        )
        .filter(pk=request_uuid)
        .first()
    )


@shared_task(
    bind=True,
    name="organizing.organizer.reactivation_requested_email",
    max_retries=5,
)
def send_reactivation_requested_emails(
    self: Any,
    *,
    request_id: str,
) -> dict[str, Any]:
    reactivation_request = _load_request(
        request_id,
    )

    if reactivation_request is None:
        return {
            "sent": False,
            "reason": "request_not_found",
        }

    organizer = reactivation_request.organizer

    if reactivation_request.status != OrganizerReactivationRequest.STATUS_PENDING:
        return {
            "sent": False,
            "reason": "request_not_pending",
        }

    sender = build_notification_sender()

    organizer_recipients = _unique_emails(
        [
            organizer.user.email,
            organizer.contact_email,
        ]
    )

    admin_recipients = _admin_emails()

    frontend_url = str(
        getattr(
            settings,
            "FRONTEND_URL",
            "http://localhost:5173",
        )
    ).rstrip("/")

    try:
        if reactivation_request.request_organizer_email_sent_at is None:
            for email in organizer_recipients:
                sender.send_email(
                    to=email,
                    subject=("[FANID] Demande de réouverture reçue"),
                    body=(
                        "Bonjour,\n\n"
                        "Votre demande de réouverture pour "
                        f"l'organisation « {organizer.org_name} » "
                        "a bien été enregistrée.\n\n"
                        "Votre compte reste suspendu tant qu'un "
                        "administrateur FANID n'a pas accepté "
                        "la demande.\n\n"
                        "Aucune réactivation automatique n'est "
                        "possible.\n\n"
                        "Vous recevrez un autre e-mail lorsque "
                        "l'administrateur aura pris sa décision.\n\n"
                        "L'équipe FANID"
                    ),
                )

            (
                OrganizerReactivationRequest.objects.filter(
                    pk=reactivation_request.pk,
                    request_organizer_email_sent_at__isnull=True,
                ).update(
                    request_organizer_email_sent_at=timezone.now(),
                )
            )

        reactivation_request.refresh_from_db()

        if reactivation_request.request_admin_email_sent_at is None:
            for email in admin_recipients:
                sender.send_email(
                    to=email,
                    subject=("[FANID] Nouvelle demande de " "réouverture organisateur"),
                    body=(
                        "Bonjour,\n\n"
                        "Une nouvelle demande de réouverture "
                        "d'un compte organisateur a été reçue.\n\n"
                        f"Organisation : {organizer.org_name}\n"
                        f"Demande : {reactivation_request.pk}\n\n"
                        "La réouverture doit être décidée "
                        "uniquement depuis l'espace administrateur.\n"
                        "L'acceptation est protégée par le code "
                        "OTP de vérification renforcée.\n\n"
                        "Ouvrir le dossier :\n"
                        f"{frontend_url}/admin/organizers/"
                        f"{organizer.pk}\n\n"
                        "L'équipe FANID"
                    ),
                )

            if admin_recipients:
                (
                    OrganizerReactivationRequest.objects.filter(
                        pk=reactivation_request.pk,
                        request_admin_email_sent_at__isnull=True,
                    ).update(
                        request_admin_email_sent_at=timezone.now(),
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
        "organizer_recipients": len(organizer_recipients),
        "admin_recipients": len(admin_recipients),
    }


@shared_task(
    bind=True,
    name="organizing.organizer.reactivation_decision_email",
    max_retries=5,
)
def send_reactivation_decision_emails(
    self: Any,
    *,
    request_id: str,
) -> dict[str, Any]:
    reactivation_request = _load_request(
        request_id,
    )

    if reactivation_request is None:
        return {
            "sent": False,
            "reason": "request_not_found",
        }

    if reactivation_request.status not in {
        OrganizerReactivationRequest.STATUS_APPROVED,
        OrganizerReactivationRequest.STATUS_REJECTED,
    }:
        return {
            "sent": False,
            "reason": "request_not_decided",
        }

    organizer = reactivation_request.organizer
    approved = reactivation_request.status == OrganizerReactivationRequest.STATUS_APPROVED

    sender = build_notification_sender()

    organizer_recipients = _unique_emails(
        [
            organizer.user.email,
            organizer.contact_email,
        ]
    )

    admin_recipients = _admin_emails()

    if approved:
        organizer_subject = "[FANID] Réouverture de votre compte approuvée"
        organizer_body = (
            "Bonjour,\n\n"
            f"La demande de réouverture de "
            f"« {organizer.org_name} » a été approuvée "
            "par un administrateur FANID.\n\n"
            "Votre espace organisateur est de nouveau actif.\n\n"
            "L'équipe FANID"
        )
        decision_text = "APPROUVÉE"
    else:
        organizer_subject = "[FANID] Demande de réouverture refusée"

        reason = reactivation_request.rejection_reason or "Aucun motif communiqué."

        organizer_body = (
            "Bonjour,\n\n"
            f"La demande de réouverture de "
            f"« {organizer.org_name} » a été refusée "
            "par un administrateur FANID.\n\n"
            f"Motif : {reason}\n\n"
            "Votre compte reste suspendu.\n\n"
            "L'équipe FANID"
        )
        decision_text = "REFUSÉE"

    try:
        if reactivation_request.decision_organizer_email_sent_at is None:
            for email in organizer_recipients:
                sender.send_email(
                    to=email,
                    subject=organizer_subject,
                    body=organizer_body,
                )

            (
                OrganizerReactivationRequest.objects.filter(
                    pk=reactivation_request.pk,
                    decision_organizer_email_sent_at__isnull=True,
                ).update(
                    decision_organizer_email_sent_at=timezone.now(),
                )
            )

        reactivation_request.refresh_from_db()

        if reactivation_request.decision_admin_email_sent_at is None:
            for email in admin_recipients:
                sender.send_email(
                    to=email,
                    subject=("[FANID] Décision de réouverture " f"{decision_text.lower()}"),
                    body=(
                        "Bonjour,\n\n"
                        "Une demande de réouverture "
                        "organisateur a été traitée.\n\n"
                        f"Organisation : {organizer.org_name}\n"
                        f"Demande : {reactivation_request.pk}\n"
                        f"Décision : {decision_text}\n\n"
                        "Cette décision est enregistrée dans "
                        "FANID pour la traçabilité.\n\n"
                        "L'équipe FANID"
                    ),
                )

            if admin_recipients:
                (
                    OrganizerReactivationRequest.objects.filter(
                        pk=reactivation_request.pk,
                        decision_admin_email_sent_at__isnull=True,
                    ).update(
                        decision_admin_email_sent_at=timezone.now(),
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
        "decision": reactivation_request.status,
        "organizer_recipients": len(organizer_recipients),
        "admin_recipients": len(admin_recipients),
    }
