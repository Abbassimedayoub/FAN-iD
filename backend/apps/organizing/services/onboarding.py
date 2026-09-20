"""
Organizer validation lifecycle.

Allowed transitions are PENDING->APPROVED, PENDING->REJECTED,
APPROVED->SUSPENDED, and SUSPENDED->APPROVED through explicit reopening.

Optimistic locking uses a conditional UPDATE on `version` so concurrent
administrative decisions cannot both succeed.
"""

from __future__ import annotations

import logging
import uuid

from django.db import transaction
from django.utils import timezone

from apps.core.concurrency import versioned_update
from apps.core.exceptions import InvalidStateTransitionError, StaleResourceError, ValidationBusinessError
from apps.core.outbox.publisher import publish_event

from ..constants import ORGANIZER_APPROVED, ORGANIZER_PENDING, ORGANIZER_REJECTED, ORGANIZER_SUSPENDED
from ..events import (
    AGGREGATE_ORGANIZER,
    ORGANIZER_APPROVED_EVENT,
    ORGANIZER_REJECTED_EVENT,
    ORGANIZER_REOPENED_EVENT,
    ORGANIZER_SUSPENDED_EVENT,
    organizer_decision_payload,
)
from ..models import Organizer

logger = logging.getLogger("fanid.organizing")


class OrganizerOnboardingService:
    """Apply administrative decisions to an organizer dossier."""

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
        """Approve the organizer account without implying that a commission agreement has been reached."""
        organizer = cls._get(organizer_id)

        if organizer.version != expected_version:
            raise StaleResourceError(
                details={
                    "current_version": organizer.version,
                }
            )

        cls._require_state(
            organizer,
            ORGANIZER_PENDING,
            ORGANIZER_APPROVED,
        )

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
            payload=organizer_decision_payload(
                status=ORGANIZER_APPROVED,
            ),
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

        publish_event(
            event_type=ORGANIZER_SUSPENDED_EVENT,
            aggregate_type=AGGREGATE_ORGANIZER,
            aggregate_id=organizer.pk,
            actor_id=actor_id,
            payload=organizer_decision_payload(
                status=ORGANIZER_SUSPENDED,
            ),
        )

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

    @classmethod
    @transaction.atomic
    def reopen(
        cls,
        *,
        organizer_id: uuid.UUID,
        actor_id: uuid.UUID,
        expected_version: int,
    ) -> Organizer:
        """Reopen a suspended organizer while preserving historical validation information and restoring only APPROVED state."""
        organizer = cls._get(organizer_id)
        cls._require_state(
            organizer,
            ORGANIZER_SUSPENDED,
            ORGANIZER_APPROVED,
        )

        new_version = versioned_update(
            model=Organizer,
            pk=organizer.pk,
            expected_version=expected_version,
            updates={
                "validation_status": ORGANIZER_APPROVED,
                "rejection_reason": None,
            },
        )

        publish_event(
            event_type=ORGANIZER_REOPENED_EVENT,
            aggregate_type=AGGREGATE_ORGANIZER,
            aggregate_id=organizer.pk,
            actor_id=actor_id,
            payload=organizer_decision_payload(
                status=ORGANIZER_APPROVED,
            ),
        )

        logger.info(
            "organizing.organizer.reopened",
            extra={
                "organizer_id": str(organizer.pk),
                "actor_id": str(actor_id),
                "version": new_version,
            },
        )

        organizer.refresh_from_db()
        return organizer
