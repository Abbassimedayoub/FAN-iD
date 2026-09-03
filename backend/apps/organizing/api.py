"""
Interface publique minimale du contexte organizing.

Les autres bounded contexts ne doivent pas importer directement les modèles
internes d organizing pour résoudre le propriétaire courant.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from .constants import (
    ORGANIZER_APPROVED,
    SCANNER_ACTIVE,
    SCANNER_DELETED,
    SCANNER_EMAIL_SENT,
    SCANNER_INVITATION_CANCELLED,
    SCANNER_INVITED,
    SCANNER_OPENED,
)
from .models import Organizer, Scanner

__all__ = [
    "OrganizerNotificationSummary",
    "ScannerAssignmentSummary",
    "ScannerPortalContext",
    "get_organizer_notification_summary",
    "get_scanner_assignment_summary",
    "get_scanner_portal_context",
    "list_scanner_assignment_summaries",
    "resolve_organizer_context",
    "resolve_organizer_commercial_context",
]


def resolve_organizer_context(
    *,
    user_id: uuid.UUID,
) -> tuple[uuid.UUID | None, bool]:
    """
    Retourne l organisateur du compte et son état d approbation.

    Un seul SELECT fournit les deux primitives nécessaires au moteur
    d autorisation.
    """

    row = (
        Organizer.objects.filter(user_id=user_id)
        .values_list(
            "pk",
            "validation_status",
        )
        .first()
    )

    if row is not None:
        organizer_id, validation_status = row

        return (
            organizer_id,
            validation_status == ORGANIZER_APPROVED,
        )

    scanner_row = (
        Scanner.objects.filter(
            user_id=user_id,
            user__is_active=True,
            user__anonymized_at__isnull=True,
            user__must_change_password=False,
            status__in=[
                "OPENED",
                "ACTIVE",
            ],
        )
        .values_list(
            "organizer_id",
            "organizer__validation_status",
        )
        .first()
    )

    if scanner_row is None:
        return None, False

    organizer_id, validation_status = scanner_row

    return (
        organizer_id,
        validation_status == ORGANIZER_APPROVED,
    )


def resolve_organizer_commercial_context(
    *,
    user_id: uuid.UUID,
) -> tuple[uuid.UUID | None, bool, bool]:
    """
    Retourne :
    (organizer_id, compte_approuve, commission_convenue).

    Le troisieme booleen ne devient vrai que si le compte est APPROVED
    ET qu'un accord financier explicite existe.
    """

    row = (
        Organizer.objects.filter(
            user_id=user_id,
        )
        .values_list(
            "pk",
            "validation_status",
            "commission_agreed_at",
        )
        .first()
    )

    if row is not None:
        (
            organizer_id,
            validation_status,
            commission_agreed_at,
        ) = row

        approved = (
            validation_status == ORGANIZER_APPROVED
        )

        return (
            organizer_id,
            approved,
            (
                approved
                and commission_agreed_at is not None
            ),
        )

    scanner_row = (
        Scanner.objects.filter(
            user_id=user_id,
            user__is_active=True,
            user__anonymized_at__isnull=True,
            user__must_change_password=False,
            status__in=[
                "OPENED",
                "ACTIVE",
            ],
        )
        .values_list(
            "organizer_id",
            "organizer__validation_status",
            "organizer__commission_agreed_at",
        )
        .first()
    )

    if scanner_row is None:
        return None, False, False

    (
        organizer_id,
        validation_status,
        commission_agreed_at,
    ) = scanner_row

    approved = (
        validation_status == ORGANIZER_APPROVED
    )

    return (
        organizer_id,
        approved,
        (
            approved
            and commission_agreed_at is not None
        ),
    )


SCANNER_EVENT_ASSIGNABLE_STATUSES = (
    SCANNER_INVITED,
    SCANNER_EMAIL_SENT,
    SCANNER_OPENED,
    SCANNER_ACTIVE,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ScannerAssignmentSummary:
    id: uuid.UUID
    organizer_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    status: str
    version: int


def _scanner_assignment_summary(
    scanner: Scanner,
) -> ScannerAssignmentSummary:
    return ScannerAssignmentSummary(
        id=scanner.pk,
        organizer_id=scanner.organizer_id,
        first_name=(scanner.invited_first_name or scanner.user.first_name),
        last_name=(scanner.invited_last_name or scanner.user.last_name),
        email=(scanner.invited_email or scanner.user.email),
        status=scanner.status,
        version=scanner.version,
    )


def get_scanner_assignment_summary(
    *,
    organizer_id: uuid.UUID,
    scanner_id: uuid.UUID,
    assignable_only: bool = False,
) -> ScannerAssignmentSummary | None:
    """
    Retourne un scanner appartenant strictement à organizer_id.

    En mode affectation, seuls les scanners encore préparables /
    opérationnels sont acceptés.
    """

    queryset = Scanner.objects.filter(
        pk=scanner_id,
        organizer_id=organizer_id,
    ).select_related("user")

    if assignable_only:
        queryset = queryset.filter(
            archived_at__isnull=True,
            status__in=(SCANNER_EVENT_ASSIGNABLE_STATUSES),
        )

    scanner = queryset.first()

    if scanner is None:
        return None

    return _scanner_assignment_summary(
        scanner,
    )


def list_scanner_assignment_summaries(
    *,
    organizer_id: uuid.UUID,
    scanner_ids: list[uuid.UUID],
) -> tuple[ScannerAssignmentSummary, ...]:
    """
    Résout les scanners d'un ensemble d'affectations sans exposer
    ceux d'un autre organisateur.
    """

    if not scanner_ids:
        return ()

    scanners = (
        Scanner.objects.filter(
            organizer_id=organizer_id,
            pk__in=scanner_ids,
            archived_at__isnull=True,
        )
        .exclude(
            status__in=(
                SCANNER_INVITATION_CANCELLED,
                SCANNER_DELETED,
            )
        )
        .select_related("user")
        .order_by(
            "created_at",
            "pk",
        )
    )

    return tuple(_scanner_assignment_summary(scanner) for scanner in scanners)


@dataclass(
    frozen=True,
    slots=True,
)
class ScannerPortalContext:
    """
    Identité minimale nécessaire au portail opérationnel scanner.

    Le portail n'est disponible qu'après remplacement du mot de passe
    temporaire et uniquement pour un scanner OPENED ou ACTIVE rattaché
    à un organisateur approuvé.
    """

    id: uuid.UUID
    organizer_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    status: str


def get_scanner_portal_context(
    *,
    user_id: uuid.UUID,
) -> ScannerPortalContext | None:
    scanner = (
        Scanner.objects.filter(
            user_id=user_id,
            user__is_active=True,
            user__anonymized_at__isnull=True,
            user__must_change_password=False,
            archived_at__isnull=True,
            organizer__validation_status=(ORGANIZER_APPROVED),
            status__in=(
                SCANNER_OPENED,
                SCANNER_ACTIVE,
            ),
        )
        .select_related(
            "user",
            "organizer",
        )
        .first()
    )

    if scanner is None:
        return None

    return ScannerPortalContext(
        id=scanner.pk,
        organizer_id=scanner.organizer_id,
        first_name=(scanner.invited_first_name or scanner.user.first_name),
        last_name=(scanner.invited_last_name or scanner.user.last_name),
        email=(scanner.invited_email or scanner.user.email),
        status=scanner.status,
    )


@dataclass(
    frozen=True,
    slots=True,
)
class OrganizerNotificationSummary:
    id: uuid.UUID
    name: str
    contact_email: str


def get_organizer_notification_summary(
    *,
    organizer_id: uuid.UUID,
) -> OrganizerNotificationSummary | None:
    organizer = (
        Organizer.objects.filter(
            pk=organizer_id,
        )
        .only(
            "id",
            "org_name",
            "contact_email",
        )
        .first()
    )

    if organizer is None:
        return None

    return OrganizerNotificationSummary(
        id=organizer.pk,
        name=organizer.org_name,
        contact_email=organizer.contact_email,
    )
