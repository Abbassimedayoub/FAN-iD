from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.outbox.publisher import publish_event

from apps.core.exceptions import (
    ConflictError,
    InvalidStateTransitionError,
    NotFoundBusinessError,
    StaleResourceError,
    ValidationBusinessError,
)

from ..constants import (
    ORGANIZER_APPROVED,
    ORGANIZER_COMMISSION_PROPOSER_ADMIN,
    ORGANIZER_COMMISSION_PROPOSER_ORGANIZER,
    ORGANIZER_PENDING,
)
from ..events import (
    AGGREGATE_ORGANIZER,
    ORGANIZER_APPROVED_EVENT,
    organizer_decision_payload,
)
from ..models import (
    Organizer,
    OrganizerCommissionProposal,
)


NEGOTIABLE_ACCOUNT_STATES = {
    ORGANIZER_PENDING,
    ORGANIZER_APPROVED,
}


class OrganizerCommissionService:
    """
    Negociation structuree Organizer <-> Admin.

    La negociation structuree porte aussi la decision d'ouverture :
    - tant qu'aucun accord n'est conclu, le dossier reste PENDING ;
    - l'acceptation finale de la commission approuve automatiquement
      le compte Organizer.
    """

    @staticmethod
    def _validate_rate(rate: Decimal) -> None:
        if rate < Decimal("0") or rate > Decimal("1"):
            raise ValidationBusinessError(
                details={
                    "commission_rate": [
                        "Le taux doit etre compris entre 0 et 1."
                    ],
                },
            )

    @staticmethod
    def _require_initial_application_state(
        organizer: Organizer,
    ) -> None:
        if organizer.validation_status != ORGANIZER_PENDING:
            raise InvalidStateTransitionError(
                details={
                    "current_state": organizer.validation_status,
                    "target_state": "COMMISSION_INITIAL_PROPOSAL",
                },
            )

    @staticmethod
    def _require_negotiable_account(
        organizer: Organizer,
    ) -> None:
        if organizer.validation_status not in NEGOTIABLE_ACCOUNT_STATES:
            raise InvalidStateTransitionError(
                details={
                    "current_state": organizer.validation_status,
                    "target_state": "COMMISSION_NEGOTIATION",
                },
            )

    @staticmethod
    def _require_not_agreed(
        organizer: Organizer,
    ) -> None:
        if organizer.commission_agreed_at is not None:
            raise ConflictError(
                code="COMMISSION_ALREADY_AGREED",
                message="La commission est deja acceptee.",
            )

    @staticmethod
    def _require_version(
        organizer: Organizer,
        expected_version: int,
    ) -> None:
        if organizer.version != expected_version:
            raise StaleResourceError(
                details={
                    "current_version": organizer.version,
                },
            )

    @staticmethod
    def _latest(
        organizer: Organizer,
    ) -> OrganizerCommissionProposal | None:
        return (
            OrganizerCommissionProposal.objects
            .filter(organizer=organizer)
            .order_by("-sequence")
            .first()
        )

    @classmethod
    def _legacy_initial(
        cls,
        organizer: Organizer,
    ) -> OrganizerCommissionProposal:
        latest = cls._latest(organizer)

        if latest is not None:
            return latest

        return OrganizerCommissionProposal.objects.create(
            organizer=organizer,
            sequence=1,
            proposed_by_id=organizer.user_id,
            proposer_role=(
                ORGANIZER_COMMISSION_PROPOSER_ORGANIZER
            ),
            rate=organizer.commission_rate,
        )

    @staticmethod
    def _require_turn(
        proposal: OrganizerCommissionProposal,
        expected_proposer: str,
    ) -> None:
        if proposal.accepted_at is not None:
            raise ConflictError(
                code="COMMISSION_ALREADY_AGREED",
                message="La commission est deja acceptee.",
            )

        if proposal.proposer_role != expected_proposer:
            raise ConflictError(
                code="COMMISSION_NEGOTIATION_TURN_INVALID",
                message=(
                    "La derniere proposition doit etre traitee "
                    "par l'autre partie."
                ),
                details={
                    "latest_proposer_role": (
                        proposal.proposer_role
                    ),
                },
            )

    @classmethod
    @transaction.atomic
    def create_initial_proposal(
        cls,
        *,
        organizer_id: uuid.UUID,
        actor_id: Any,
        rate: Decimal,
    ) -> OrganizerCommissionProposal:
        cls._validate_rate(rate)

        organizer = (
            Organizer.objects
            .select_for_update()
            .filter(
                pk=organizer_id,
                user_id=actor_id,
            )
            .first()
        )

        if organizer is None:
            raise NotFoundBusinessError()

        cls._require_initial_application_state(
            organizer,
        )
        cls._require_not_agreed(
            organizer,
        )

        if OrganizerCommissionProposal.objects.filter(
            organizer=organizer,
        ).exists():
            raise ConflictError(
                code="COMMISSION_INITIAL_PROPOSAL_ALREADY_EXISTS",
                message="Une proposition initiale existe deja.",
            )

        return OrganizerCommissionProposal.objects.create(
            organizer=organizer,
            sequence=1,
            proposed_by_id=actor_id,
            proposer_role=(
                ORGANIZER_COMMISSION_PROPOSER_ORGANIZER
            ),
            rate=rate,
        )

    @classmethod
    @transaction.atomic
    def admin_counter(
        cls,
        *,
        organizer_id: uuid.UUID,
        actor_id: Any,
        expected_version: int,
        rate: Decimal,
    ) -> Organizer:
        cls._validate_rate(rate)

        organizer = (
            Organizer.objects
            .select_for_update()
            .get(pk=organizer_id)
        )

        cls._require_version(
            organizer,
            expected_version,
        )
        cls._require_negotiable_account(
            organizer,
        )
        cls._require_not_agreed(
            organizer,
        )

        latest = cls._legacy_initial(
            organizer,
        )

        cls._require_turn(
            latest,
            ORGANIZER_COMMISSION_PROPOSER_ORGANIZER,
        )

        OrganizerCommissionProposal.objects.create(
            organizer=organizer,
            sequence=latest.sequence + 1,
            proposed_by_id=actor_id,
            proposer_role=(
                ORGANIZER_COMMISSION_PROPOSER_ADMIN
            ),
            rate=rate,
        )

        organizer.version += 1
        organizer.save(
            update_fields=[
                "version",
                "updated_at",
            ],
        )

        return organizer

    @classmethod
    @transaction.atomic
    def organizer_counter(
        cls,
        *,
        organizer_id: uuid.UUID,
        actor_id: Any,
        expected_version: int,
        rate: Decimal,
    ) -> Organizer:
        cls._validate_rate(rate)

        organizer = (
            Organizer.objects
            .select_for_update()
            .filter(
                pk=organizer_id,
                user_id=actor_id,
            )
            .first()
        )

        if organizer is None:
            raise NotFoundBusinessError()

        cls._require_version(
            organizer,
            expected_version,
        )
        cls._require_negotiable_account(
            organizer,
        )
        cls._require_not_agreed(
            organizer,
        )

        latest = cls._latest(
            organizer,
        )

        if latest is None:
            raise ConflictError(
                code="COMMISSION_ADMIN_PROPOSAL_REQUIRED",
                message=(
                    "Aucune contre-proposition administrateur "
                    "n'est en attente."
                ),
            )

        cls._require_turn(
            latest,
            ORGANIZER_COMMISSION_PROPOSER_ADMIN,
        )

        OrganizerCommissionProposal.objects.create(
            organizer=organizer,
            sequence=latest.sequence + 1,
            proposed_by_id=actor_id,
            proposer_role=(
                ORGANIZER_COMMISSION_PROPOSER_ORGANIZER
            ),
            rate=rate,
        )

        organizer.version += 1
        organizer.save(
            update_fields=[
                "version",
                "updated_at",
            ],
        )

        return organizer

    @classmethod
    def _accept(
        cls,
        *,
        organizer: Organizer,
        proposal: OrganizerCommissionProposal,
        accepted_by_id: Any,
    ) -> Organizer:
        now = timezone.now()

        proposal.accepted_at = now
        proposal.accepted_by_id = accepted_by_id
        proposal.save(
            update_fields=[
                "accepted_at",
                "accepted_by",
                "updated_at",
            ],
        )

        auto_approve = organizer.validation_status == ORGANIZER_PENDING

        approval_actor_id = (
            proposal.proposed_by_id
            if proposal.proposer_role
            == ORGANIZER_COMMISSION_PROPOSER_ADMIN
            else accepted_by_id
        )

        organizer.commission_rate = proposal.rate
        organizer.commission_agreed_at = now
        organizer.version += 1

        update_fields = [
            "commission_rate",
            "commission_agreed_at",
            "version",
            "updated_at",
        ]

        if auto_approve:
            organizer.validation_status = ORGANIZER_APPROVED
            organizer.rejection_reason = None
            organizer.validated_at = now
            organizer.validated_by_id = approval_actor_id

            update_fields.extend(
                [
                    "validation_status",
                    "rejection_reason",
                    "validated_at",
                    "validated_by",
                ],
            )

        organizer.save(
            update_fields=update_fields,
        )

        if auto_approve:
            publish_event(
                event_type=ORGANIZER_APPROVED_EVENT,
                aggregate_type=AGGREGATE_ORGANIZER,
                aggregate_id=organizer.pk,
                actor_id=approval_actor_id,
                payload=organizer_decision_payload(
                    status=ORGANIZER_APPROVED,
                ),
            )

        return organizer

    @classmethod
    @transaction.atomic
    def admin_accept(
        cls,
        *,
        organizer_id: uuid.UUID,
        actor_id: Any,
        expected_version: int,
    ) -> Organizer:
        organizer = (
            Organizer.objects
            .select_for_update()
            .get(pk=organizer_id)
        )

        cls._require_version(
            organizer,
            expected_version,
        )
        cls._require_negotiable_account(
            organizer,
        )
        cls._require_not_agreed(
            organizer,
        )

        latest = cls._legacy_initial(
            organizer,
        )

        cls._require_turn(
            latest,
            ORGANIZER_COMMISSION_PROPOSER_ORGANIZER,
        )

        return cls._accept(
            organizer=organizer,
            proposal=latest,
            accepted_by_id=actor_id,
        )

    @classmethod
    @transaction.atomic
    def organizer_accept(
        cls,
        *,
        organizer_id: uuid.UUID,
        actor_id: Any,
        expected_version: int,
    ) -> Organizer:
        organizer = (
            Organizer.objects
            .select_for_update()
            .filter(
                pk=organizer_id,
                user_id=actor_id,
            )
            .first()
        )

        if organizer is None:
            raise NotFoundBusinessError()

        cls._require_version(
            organizer,
            expected_version,
        )
        cls._require_negotiable_account(
            organizer,
        )
        cls._require_not_agreed(
            organizer,
        )

        latest = cls._latest(
            organizer,
        )

        if latest is None:
            raise ConflictError(
                code="COMMISSION_ADMIN_PROPOSAL_REQUIRED",
                message=(
                    "Aucune contre-proposition administrateur "
                    "n'est en attente."
                ),
            )

        cls._require_turn(
            latest,
            ORGANIZER_COMMISSION_PROPOSER_ADMIN,
        )

        return cls._accept(
            organizer=organizer,
            proposal=latest,
            accepted_by_id=actor_id,
        )
