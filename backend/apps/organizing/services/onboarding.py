"""
Cycle de validation d un organisateur.

Transitions autorisees pour S1-A.8b :

    PENDING  -> APPROVED
    PENDING  -> REJECTED
    APPROVED -> SUSPENDED

Toutes les autres transitions sont refusees explicitement.

Le verrou optimiste repose sur un UPDATE conditionnel par `version`. Lire une
version puis appeler `save()` ne suffirait pas : deux administrateurs pourraient
lire la meme version avant que l un des deux n ecrive.
"""

from __future__ import annotations

import logging
import uuid

from django.db import transaction
from django.utils import timezone

from apps.core.concurrency import versioned_update
from apps.core.exceptions import InvalidStateTransitionError, ValidationBusinessError
from apps.core.outbox.publisher import publish_event

from ..constants import ORGANIZER_APPROVED, ORGANIZER_PENDING, ORGANIZER_REJECTED, ORGANIZER_SUSPENDED
from ..events import (
    AGGREGATE_ORGANIZER,
    ORGANIZER_APPROVED_EVENT,
    ORGANIZER_REJECTED_EVENT,
    organizer_decision_payload,
)
from ..models import Organizer

logger = logging.getLogger("fanid.organizing")


class OrganizerOnboardingService:
    """Applique les decisions administratives sur un dossier organisateur."""

    @staticmethod
    def _get(organizer_id: uuid.UUID) -> Organizer:
        return Organizer.objects.get(pk=organizer_id)

    @staticmethod
    def _require_state(organizer: Organizer, expected: str, target: str) -> None:
        if organizer.validation_status != expected:
            raise InvalidStateTransitionError(
                details={
                    "current_state": organizer.validation_status,
                    "target_state": target,
                }
            )

    @classmethod
    @transaction.atomic
    def approve(
        cls,
        *,
        organizer_id: uuid.UUID,
        actor_id: uuid.UUID,
        expected_version: int,
    ) -> Organizer:
        organizer = cls._get(organizer_id)
        cls._require_state(organizer, ORGANIZER_PENDING, ORGANIZER_APPROVED)

        now = timezone.now()
        new_version = versioned_update(
            model=Organizer,
            pk=organizer.pk,
            expected_version=expected_version,
            updates={
                "validation_status": ORGANIZER_APPROVED,
                "rejection_reason": None,
                "validated_at": now,
                "validated_by_id": actor_id,
            },
        )

        publish_event(
            event_type=ORGANIZER_APPROVED_EVENT,
            aggregate_type=AGGREGATE_ORGANIZER,
            aggregate_id=organizer.pk,
            actor_id=actor_id,
            payload=organizer_decision_payload(status=ORGANIZER_APPROVED),
        )

        logger.info(
            "organizing.organizer.approved",
            extra={
                "organizer_id": str(organizer.pk),
                "actor_id": str(actor_id),
                "version": new_version,
            },
        )

        organizer.refresh_from_db()
        return organizer

    @classmethod
    @transaction.atomic
    def reject(
        cls,
        *,
        organizer_id: uuid.UUID,
        actor_id: uuid.UUID,
        expected_version: int,
        reason: str,
    ) -> Organizer:
        reason = reason.strip()
        if not reason:
            raise ValidationBusinessError(details={"reason": ["Ce champ est obligatoire."]})

        organizer = cls._get(organizer_id)
        cls._require_state(organizer, ORGANIZER_PENDING, ORGANIZER_REJECTED)

        now = timezone.now()
        new_version = versioned_update(
            model=Organizer,
            pk=organizer.pk,
            expected_version=expected_version,
            updates={
                "validation_status": ORGANIZER_REJECTED,
                "rejection_reason": reason,
                "validated_at": now,
                "validated_by_id": actor_id,
            },
        )

        publish_event(
            event_type=ORGANIZER_REJECTED_EVENT,
            aggregate_type=AGGREGATE_ORGANIZER,
            aggregate_id=organizer.pk,
            actor_id=actor_id,
            payload=organizer_decision_payload(status=ORGANIZER_REJECTED),
        )

        logger.info(
            "organizing.organizer.rejected",
            extra={
                "organizer_id": str(organizer.pk),
                "actor_id": str(actor_id),
                "version": new_version,
            },
        )

        organizer.refresh_from_db()
        return organizer

    @classmethod
    @transaction.atomic
    def suspend(
        cls,
        *,
        organizer_id: uuid.UUID,
        actor_id: uuid.UUID,
        expected_version: int,
    ) -> Organizer:
        organizer = cls._get(organizer_id)
        cls._require_state(organizer, ORGANIZER_APPROVED, ORGANIZER_SUSPENDED)

        new_version = versioned_update(
            model=Organizer,
            pk=organizer.pk,
            expected_version=expected_version,
            updates={"validation_status": ORGANIZER_SUSPENDED},
        )

        # Deliberement PAS d evenement Outbox pour la suspension dans ce lot.
        logger.info(
            "organizing.organizer.suspended",
            extra={
                "organizer_id": str(organizer.pk),
                "actor_id": str(actor_id),
                "version": new_version,
            },
        )

        organizer.refresh_from_db()
        return organizer
