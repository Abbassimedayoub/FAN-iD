from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import (
    ConflictError,
    NotFoundBusinessError,
)

from .constants import ORGANIZER_SUSPENDED
from .models import Organizer, OrganizerReactivationRequest
from .services.onboarding import OrganizerOnboardingService


def _schedule_requested_email(
    request_id: uuid.UUID,
) -> None:
    from .reactivation_tasks import (
        send_reactivation_requested_emails,
    )

    request_id_text = str(request_id)

    transaction.on_commit(
        lambda: send_reactivation_requested_emails.delay(
            request_id=request_id_text,
        )
    )


def _schedule_decision_email(
    request_id: uuid.UUID,
) -> None:
    from .reactivation_tasks import (
        send_reactivation_decision_emails,
    )

    request_id_text = str(request_id)

    transaction.on_commit(
        lambda: send_reactivation_decision_emails.delay(
            request_id=request_id_text,
        )
    )


class OrganizerReactivationService:
    """
    Cycle de réouverture d'un organisateur suspendu.

    L'organisateur peut uniquement CREER une demande.
    Il ne change jamais lui-même son validation_status.

    Seul un administrateur peut ensuite approuver/refuser.
    L'autorisation OTP/STEP_UP de l'administrateur est appliquée
    par les vues via Action.ORGANIZER_APPROVE / REJECT.
    """

    @staticmethod
    @transaction.atomic
    def request(
        *,
        organizer_id: uuid.UUID,
        requested_by_id: Any,
    ) -> tuple[OrganizerReactivationRequest, bool]:
        organizer = (
            Organizer.objects.select_for_update()
            .filter(
                pk=organizer_id,
                user_id=requested_by_id,
            )
            .first()
        )

        if organizer is None:
            raise NotFoundBusinessError()

        if organizer.validation_status != ORGANIZER_SUSPENDED:
            raise ConflictError(
                code="ORGANIZER_REACTIVATION_NOT_ALLOWED",
                message=(
                    "Une demande de réouverture est possible " "uniquement pour un organisateur suspendu."
                ),
            )

        existing = (
            OrganizerReactivationRequest.objects.select_for_update()
            .filter(
                organizer=organizer,
                status=(OrganizerReactivationRequest.STATUS_PENDING),
            )
            .order_by("-created_at")
            .first()
        )

        if existing is not None:
            return existing, False

        reactivation_request = OrganizerReactivationRequest.objects.create(
            organizer=organizer,
            requested_by_id=requested_by_id,
            organizer_version=organizer.version,
            status=(OrganizerReactivationRequest.STATUS_PENDING),
        )

        _schedule_requested_email(
            reactivation_request.pk,
        )

        return reactivation_request, True

    @staticmethod
    @transaction.atomic
    def approve(
        *,
        organizer_id: uuid.UUID,
        reviewed_by_id: Any,
        expected_version: int,
    ) -> tuple[
        OrganizerReactivationRequest,
        Organizer,
    ]:
        organizer = Organizer.objects.select_for_update().filter(pk=organizer_id).first()

        if organizer is None:
            raise NotFoundBusinessError()

        reactivation_request = (
            OrganizerReactivationRequest.objects.select_for_update()
            .filter(
                organizer=organizer,
                status=(OrganizerReactivationRequest.STATUS_PENDING),
            )
            .order_by("-created_at")
            .first()
        )

        if reactivation_request is None:
            raise ConflictError(
                code="ORGANIZER_REACTIVATION_REQUEST_NOT_PENDING",
                message=("Aucune demande de réouverture " "n'est actuellement en attente."),
            )

        if organizer.validation_status != ORGANIZER_SUSPENDED:
            raise ConflictError(
                code="ORGANIZER_REACTIVATION_NOT_ALLOWED",
                message=("Cet organisateur n'est plus suspendu."),
            )

        reopened = OrganizerOnboardingService.reopen(
            organizer_id=organizer.pk,
            actor_id=reviewed_by_id,
            expected_version=expected_version,
        )

        now = timezone.now()

        reactivation_request.status = OrganizerReactivationRequest.STATUS_APPROVED
        reactivation_request.reviewed_by_id = reviewed_by_id
        reactivation_request.reviewed_at = now
        reactivation_request.rejection_reason = None

        reactivation_request.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "rejection_reason",
                "updated_at",
            ]
        )

        _schedule_decision_email(
            reactivation_request.pk,
        )

        return reactivation_request, reopened

    @staticmethod
    @transaction.atomic
    def reject(
        *,
        organizer_id: uuid.UUID,
        reviewed_by_id: Any,
        expected_version: int,
        reason: str,
    ) -> OrganizerReactivationRequest:
        organizer = Organizer.objects.select_for_update().filter(pk=organizer_id).first()

        if organizer is None:
            raise NotFoundBusinessError()

        if organizer.version != expected_version:
            raise ConflictError(
                code="STALE_RESOURCE",
                message=("Le dossier a été modifié. " "Rechargez-le avant de réessayer."),
            )

        reactivation_request = (
            OrganizerReactivationRequest.objects.select_for_update()
            .filter(
                organizer=organizer,
                status=(OrganizerReactivationRequest.STATUS_PENDING),
            )
            .order_by("-created_at")
            .first()
        )

        if reactivation_request is None:
            raise ConflictError(
                code="ORGANIZER_REACTIVATION_REQUEST_NOT_PENDING",
                message=("Aucune demande de réouverture " "n'est actuellement en attente."),
            )

        if organizer.validation_status != ORGANIZER_SUSPENDED:
            raise ConflictError(
                code="ORGANIZER_REACTIVATION_NOT_ALLOWED",
                message=("Cet organisateur n'est plus suspendu."),
            )

        now = timezone.now()

        reactivation_request.status = OrganizerReactivationRequest.STATUS_REJECTED
        reactivation_request.reviewed_by_id = reviewed_by_id
        reactivation_request.reviewed_at = now
        reactivation_request.rejection_reason = reason.strip()

        reactivation_request.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "rejection_reason",
                "updated_at",
            ]
        )

        _schedule_decision_email(
            reactivation_request.pk,
        )

        return reactivation_request
