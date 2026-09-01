from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import (
    ConflictError,
    NotFoundBusinessError,
    StaleResourceError,
)
from apps.core.outbox.publisher import publish_event

from ..constants import (
    SCANNER_ACTIVE,
    SCANNER_LEAVE_REQUESTED,
)
from ..events import (
    AGGREGATE_SCANNER,
    SCANNER_LEAVE_REJECTED_EVENT,
    SCANNER_LEAVE_REQUESTED_EVENT,
    scanner_leave_rejected_payload,
    scanner_leave_request_payload,
)
from ..models import Organizer, Scanner
from .scanners import ScannerAccessService


class ScannerLeaveService:
    @staticmethod
    def get_request_scanner(
        *,
        user_id: Any,
    ) -> Scanner:
        scanner = (
            Scanner.objects.select_related(
                "user",
                "organizer",
            )
            .filter(
                user_id=user_id,
                archived_at__isnull=True,
            )
            .first()
        )

        if scanner is None:
            raise NotFoundBusinessError()

        return scanner

    @staticmethod
    def request(
        *,
        user_id: Any,
    ) -> Scanner:
        with transaction.atomic():
            scanner = (
                Scanner.objects.select_for_update()
                .select_related(
                    "user",
                    "organizer",
                )
                .filter(
                    user_id=user_id,
                    archived_at__isnull=True,
                )
                .first()
            )

            if scanner is None:
                raise NotFoundBusinessError()

            if scanner.status == SCANNER_LEAVE_REQUESTED:
                raise ConflictError(
                    code="SCANNER_LEAVE_ALREADY_REQUESTED",
                    message="Une demande de départ est déjà en attente.",
                )

            if scanner.status != SCANNER_ACTIVE:
                raise ConflictError(
                    code="SCANNER_LEAVE_NOT_ALLOWED",
                    message=(
                        "La demande de départ est disponible " "uniquement pour un compte scanner actif."
                    ),
                )

            scanner.status = SCANNER_LEAVE_REQUESTED
            scanner.leave_requested_at = timezone.now()
            scanner.leave_rejected_at = None

            # Une nouvelle demande après un précédent refus
            # doit pouvoir renvoyer ses propres notifications.
            scanner.leave_request_scanner_email_sent_at = None
            scanner.leave_request_organizer_email_sent_at = None
            scanner.leave_rejected_scanner_email_sent_at = None
            scanner.leave_rejected_organizer_email_sent_at = None

            scanner.version += 1

            scanner.save(
                update_fields=[
                    "status",
                    "leave_requested_at",
                    "leave_rejected_at",
                    "leave_request_scanner_email_sent_at",
                    "leave_request_organizer_email_sent_at",
                    "leave_rejected_scanner_email_sent_at",
                    "leave_rejected_organizer_email_sent_at",
                    "version",
                    "updated_at",
                ],
            )

            publish_event(
                event_type=SCANNER_LEAVE_REQUESTED_EVENT,
                aggregate_type=AGGREGATE_SCANNER,
                aggregate_id=scanner.pk,
                actor_id=user_id,
                payload=scanner_leave_request_payload(),
            )

        return scanner

    @staticmethod
    def reject(
        *,
        organizer: Organizer,
        scanner_id: uuid.UUID,
        actor_id: Any,
        expected_version: int,
    ) -> Scanner:
        with transaction.atomic():
            scanner = (
                Scanner.objects.select_for_update()
                .filter(
                    pk=scanner_id,
                    organizer=organizer,
                    archived_at__isnull=True,
                )
                .first()
            )

            if scanner is None:
                raise NotFoundBusinessError()

            if scanner.version != expected_version:
                raise StaleResourceError(
                    details={
                        "current_version": scanner.version,
                    },
                )

            if scanner.status != SCANNER_LEAVE_REQUESTED:
                raise ConflictError(
                    code="SCANNER_LEAVE_REQUEST_NOT_PENDING",
                    message="Aucune demande de départ n'est en attente.",
                )

            scanner.status = SCANNER_ACTIVE
            scanner.leave_rejected_at = timezone.now()
            scanner.version += 1

            scanner.save(
                update_fields=[
                    "status",
                    "leave_rejected_at",
                    "version",
                    "updated_at",
                ],
            )

            publish_event(
                event_type=SCANNER_LEAVE_REJECTED_EVENT,
                aggregate_type=AGGREGATE_SCANNER,
                aggregate_id=scanner.pk,
                actor_id=actor_id,
                payload=scanner_leave_rejected_payload(),
            )

        return scanner

    @staticmethod
    def accept(
        *,
        organizer: Organizer,
        scanner_id: uuid.UUID,
        actor_id: Any,
        expected_version: int,
    ) -> Scanner:
        # La révocation existante reste l'unique endroit
        # responsable de la désactivation, de l'anonymisation
        # et de la révocation des sessions.
        return ScannerAccessService.revoke(
            organizer=organizer,
            scanner_id=scanner_id,
            actor_id=actor_id,
            expected_version=expected_version,
            required_status=SCANNER_LEAVE_REQUESTED,
        )
