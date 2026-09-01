from __future__ import annotations

import uuid
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.exceptions import ConflictError, NotFoundBusinessError
from apps.core.outbox.publisher import publish_event
from apps.identity.api import rotate_scanner_temporary_password

from ..constants import (
    SCANNER_CREDENTIAL_REQUEST_FULFILLED,
    SCANNER_CREDENTIAL_REQUEST_PENDING,
    SCANNER_DELETED,
    SCANNER_INVITATION_CANCELLED,
)
from ..events import (
    AGGREGATE_SCANNER,
    SCANNER_PASSWORD_HELP_REQUESTED_EVENT,
    SCANNER_TEMP_PASSWORD_REISSUED_EVENT,
    scanner_password_help_requested_payload,
    scanner_temp_password_reissued_payload,
)
from ..models import Organizer, Scanner, ScannerCredentialRequest


class ScannerCredentialService:
    @staticmethod
    def request_help(
        *,
        email: str,
    ) -> None:
        """
        Réponse générique côté API.

        Une adresse inconnue ou supprimée ne doit
        jamais permettre d'énumérer les comptes.
        """

        normalized = email.strip()

        scanner = (
            Scanner.objects.select_related(
                "user",
                "organizer",
            )
            .filter(
                Q(invited_email__iexact=normalized) | Q(user__email__iexact=normalized),
                user__is_active=True,
                user__anonymized_at__isnull=True,
            )
            .exclude(
                status__in=[
                    SCANNER_INVITATION_CANCELLED,
                    SCANNER_DELETED,
                ],
            )
            .order_by("-created_at")
            .first()
        )

        if scanner is None:
            return

        try:
            with transaction.atomic():
                request = ScannerCredentialRequest.objects.create(
                    scanner=scanner,
                    status=(SCANNER_CREDENTIAL_REQUEST_PENDING),
                )

                publish_event(
                    event_type=(SCANNER_PASSWORD_HELP_REQUESTED_EVENT),
                    aggregate_type=AGGREGATE_SCANNER,
                    aggregate_id=scanner.pk,
                    actor_id=None,
                    payload=(
                        scanner_password_help_requested_payload(
                            request_id=request.pk,
                        )
                    ),
                )

        except IntegrityError:
            # Une demande PENDING existe déjà.
            # Même réponse générique.
            return

    @staticmethod
    def reissue(
        *,
        organizer: Organizer,
        scanner_id: uuid.UUID,
        actor_id: Any,
    ) -> ScannerCredentialRequest:
        with transaction.atomic():
            scanner = (
                Scanner.objects.select_for_update()
                .select_related("user")
                .filter(
                    pk=scanner_id,
                    organizer=organizer,
                )
                .exclude(
                    status__in=[
                        SCANNER_INVITATION_CANCELLED,
                        SCANNER_DELETED,
                    ],
                )
                .first()
            )

            if scanner is None:
                raise NotFoundBusinessError()

            request = (
                ScannerCredentialRequest.objects.select_for_update()
                .filter(
                    scanner=scanner,
                    status=(SCANNER_CREDENTIAL_REQUEST_PENDING),
                )
                .order_by("-created_at")
                .first()
            )

            if request is None:
                raise ConflictError(
                    code=("SCANNER_PASSWORD_HELP_NOT_REQUESTED"),
                    message=("Aucune demande de nouveau " "mot de passe n'est en attente."),
                )

            generation = rotate_scanner_temporary_password(
                user_id=scanner.user_id,
                invitation_id=scanner.pk,
            )

            request.status = SCANNER_CREDENTIAL_REQUEST_FULFILLED
            request.resolved_at = timezone.now()
            request.resolved_by_id = actor_id
            request.generation = generation

            request.save(
                update_fields=[
                    "status",
                    "resolved_at",
                    "resolved_by",
                    "generation",
                    "updated_at",
                ],
            )

            publish_event(
                event_type=(SCANNER_TEMP_PASSWORD_REISSUED_EVENT),
                aggregate_type=AGGREGATE_SCANNER,
                aggregate_id=scanner.pk,
                actor_id=actor_id,
                payload=(
                    scanner_temp_password_reissued_payload(
                        request_id=request.pk,
                        generation=generation,
                    )
                ),
            )

        return request
