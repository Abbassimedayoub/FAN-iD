"""
Minimal public interface for the organizing context.

Other bounded contexts resolve current ownership through this API rather than
importing organizing's internal models directly.
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
    "resolve_active_scanner_id",
    "resolve_organizer_context",
    "resolve_organizer_commercial_context",
]


def resolve_organizer_context(
    *,
    user_id: uuid.UUID,
) -> tuple[uuid.UUID | None, bool]:
    """Return the account's organizer identifier and approval state in one query."""

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
    """Return organizer_id, account approval state, and whether an explicit commission agreement exists."""

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

        approved = validation_status == ORGANIZER_APPROVED

        return (
            organizer_id,
            approved,
            (approved and commission_agreed_at is not None),
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

    approved = validation_status == ORGANIZER_APPROVED

    return (
        organizer_id,
        approved,
        (approved and commission_agreed_at is not None),
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
    Return a scanner strictly owned by organizer_id; assignment mode accepts only operationally
    eligible scanners.
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
    """Resolve scanners for assignments without exposing scanners from another organizer."""

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
    Return the minimal scanner identity required by the operational portal after temporary-password
    replacement and organizer approval.
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


def resolve_active_scanner_id(
    *,
    user_id: uuid.UUID,
) -> uuid.UUID | None:
    """Return the active scanner associated with the authenticated user."""
    return (
        Scanner.objects.filter(
            user_id=user_id,
            user__is_active=True,
            user__anonymized_at__isnull=True,
            user__must_change_password=False,
            status=SCANNER_ACTIVE,
            removed_at__isnull=True,
            archived_at__isnull=True,
        )
        .values_list("pk", flat=True)
        .first()
    )
