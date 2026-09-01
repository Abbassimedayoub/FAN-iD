from __future__ import annotations

import uuid
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import ConflictError, NotFoundBusinessError, StaleResourceError
from apps.core.outbox.publisher import publish_event
from apps.identity.api import (
    create_invited_scanner_account,
    deactivate_scanner_account,
    derive_scanner_temporary_password,
    rotate_scanner_temporary_password,
)

from ..constants import (
    SCANNER_ACTIVE,
    SCANNER_DELETED,
    SCANNER_EMAIL_SENT,
    SCANNER_INVITATION_CANCELLED,
    SCANNER_INVITED,
    SCANNER_LEAVE_REQUESTED,
    SCANNER_OPENED,
)
from ..events import (
    AGGREGATE_SCANNER,
    SCANNER_INVITATION_REISSUED_EVENT,
    SCANNER_INVITED_EVENT,
    SCANNER_REVOKED_EVENT,
    scanner_invitation_reissued_payload,
    scanner_invited_payload,
    scanner_revoked_payload,
)
from ..models import Organizer, Scanner


class ScannerInvitationService:
    @staticmethod
    def invite(
        *,
        organizer: Organizer,
        actor_id: Any,
        first_name: str,
        last_name: str,
        email: str,
    ) -> Scanner:
        scanner_id = uuid.uuid4()

        clean_first_name = first_name.strip()
        clean_last_name = last_name.strip()
        clean_email = email.strip()

        existing_scanner = (
            Scanner.objects.filter(
                organizer=organizer,
                invited_email__iexact=clean_email,
                archived_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )

        if existing_scanner is not None:
            if existing_scanner.status in {
                SCANNER_INVITED,
                SCANNER_EMAIL_SENT,
                SCANNER_OPENED,
            }:
                raise ConflictError(
                    code="SCANNER_INVITATION_ALREADY_EXISTS",
                    message=(
                        "Une invitation a déjà été envoyée à ce compte. "
                        "Vous pouvez la renvoyer depuis sa fiche scanner."
                    ),
                )

            if existing_scanner.status in {
                SCANNER_ACTIVE,
                SCANNER_LEAVE_REQUESTED,
            }:
                raise ConflictError(
                    code="SCANNER_ALREADY_IN_TEAM",
                    message=("Ce compte fait déjà partie de votre équipe scanner."),
                )

        temporary_password = derive_scanner_temporary_password(
            invitation_id=scanner_id,
        )

        try:
            with transaction.atomic():
                user_id = create_invited_scanner_account(
                    email=clean_email,
                    first_name=clean_first_name,
                    last_name=clean_last_name,
                    temporary_password=(temporary_password),
                )

                scanner = Scanner.objects.create(
                    id=scanner_id,
                    organizer=organizer,
                    user_id=user_id,
                    invited_by_id=actor_id,
                    invited_first_name=(clean_first_name),
                    invited_last_name=(clean_last_name),
                    invited_email=clean_email,
                )

                publish_event(
                    event_type=SCANNER_INVITED_EVENT,
                    aggregate_type=AGGREGATE_SCANNER,
                    aggregate_id=scanner.pk,
                    actor_id=actor_id,
                    payload=scanner_invited_payload(),
                )

        except IntegrityError as exc:
            raise ConflictError(
                code="SCANNER_EMAIL_ALREADY_USED",
                message=("Cette adresse e-mail est déjà " "associée à un compte FANID."),
            ) from exc

        return scanner

    @staticmethod
    def resend(
        *,
        organizer: Organizer,
        actor_id: Any,
        scanner_id: uuid.UUID,
    ) -> Scanner:
        """
        Renvoie une invitation pré-active avec
        un NOUVEAU secret temporaire.

        Ce flux est distinct de la récupération
        demandée par un scanner actif.
        """

        pre_active = {
            SCANNER_INVITED,
            SCANNER_EMAIL_SENT,
            SCANNER_OPENED,
        }

        with transaction.atomic():
            scanner = (
                Scanner.objects.select_for_update()
                .select_related("user")
                .filter(
                    pk=scanner_id,
                    organizer=organizer,
                )
                .first()
            )

            if scanner is None:
                raise NotFoundBusinessError()

            if scanner.status not in pre_active:
                raise ConflictError(
                    code=("SCANNER_INVITATION_RESEND_NOT_ALLOWED"),
                    message=(
                        "L'invitation ne peut être " "renvoyée que tant que le " "scanner n'est pas actif."
                    ),
                )

            if not scanner.user.is_active or scanner.user.anonymized_at is not None:
                raise ConflictError(
                    code=("SCANNER_INVITATION_RESEND_NOT_ALLOWED"),
                    message=("Ce compte scanner n'est " "plus disponible."),
                )

            generation = rotate_scanner_temporary_password(
                user_id=scanner.user_id,
                invitation_id=scanner.pk,
            )

            publish_event(
                event_type=(SCANNER_INVITATION_REISSUED_EVENT),
                aggregate_type=AGGREGATE_SCANNER,
                aggregate_id=scanner.pk,
                actor_id=actor_id,
                payload=(
                    scanner_invitation_reissued_payload(
                        generation=generation,
                    )
                ),
            )

        return scanner


class ScannerAccessService:
    PRE_ACTIVE = {
        SCANNER_INVITED,
        SCANNER_EMAIL_SENT,
        SCANNER_OPENED,
    }

    TERMINAL = {
        SCANNER_INVITATION_CANCELLED,
        SCANNER_DELETED,
    }

    @staticmethod
    def revoke(
        *,
        organizer: Organizer,
        scanner_id: uuid.UUID,
        actor_id: Any,
        expected_version: int,
        required_status: str | None = None,
    ) -> Scanner:
        with transaction.atomic():
            scanner = (
                Scanner.objects.select_for_update()
                .select_related("user")
                .filter(
                    pk=scanner_id,
                    organizer=organizer,
                )
                .first()
            )

            if scanner is None:
                raise NotFoundBusinessError()

            if scanner.version != expected_version:
                raise StaleResourceError(
                    details={
                        "current_version": (scanner.version),
                    },
                )

            if required_status is not None and scanner.status != required_status:
                raise ConflictError(
                    code="SCANNER_LEAVE_REQUEST_NOT_PENDING",
                    message="Aucune demande de départ n'est en attente.",
                )

            if scanner.status in (ScannerAccessService.TERMINAL):
                raise ConflictError(
                    code="SCANNER_ALREADY_REMOVED",
                    message=("Ce scanner a déjà été " "retiré."),
                )

            user = scanner.user

            # Toujours capturer les coordonnées
            # avant anonymisation.
            scanner.invited_first_name = scanner.invited_first_name or user.first_name
            scanner.invited_last_name = scanner.invited_last_name or user.last_name
            scanner.invited_email = scanner.invited_email or user.email

            # Le changement de mot de passe peut
            # avoir eu lieu avant que le consumer
            # asynchrone ne passe OPENED -> ACTIVE.
            account_is_active = not user.must_change_password or scanner.status in {
                SCANNER_ACTIVE,
                SCANNER_LEAVE_REQUESTED,
            }

            if account_is_active:
                target_status = SCANNER_DELETED
            else:
                target_status = SCANNER_INVITATION_CANCELLED

            scanner.status = target_status
            scanner.removed_at = timezone.now()
            scanner.removed_by_id = actor_id
            scanner.version += 1

            scanner.save(
                update_fields=[
                    "invited_first_name",
                    "invited_last_name",
                    "invited_email",
                    "status",
                    "removed_at",
                    "removed_by",
                    "version",
                    "updated_at",
                ],
            )

            sessions_revoked = deactivate_scanner_account(
                user_id=scanner.user_id,
            )

            publish_event(
                event_type=SCANNER_REVOKED_EVENT,
                aggregate_type=AGGREGATE_SCANNER,
                aggregate_id=scanner.pk,
                actor_id=actor_id,
                payload=scanner_revoked_payload(
                    organizer_id=organizer.pk,
                    status=target_status,
                    sessions_revoked=(sessions_revoked),
                ),
            )

        return scanner
