from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.catalog.api import is_scanner_assigned_to_event
from apps.core.exceptions import ConflictError, PermissionBusinessError, ValidationBusinessError
from apps.organizing.api import resolve_active_scanner_id
from apps.ticketing.api import lock_ticket_for_admission, mark_ticket_used, parse_ticket_qr_identity

from ..models import TicketAdmission
from .admission_sessions import require_event_admission_open


class InvalidTicketQrError(ValidationBusinessError):
    default_code = "INVALID_TICKET_QR"
    default_message = "Le QR présenté est invalide ou expiré."


class TicketAlreadyAdmittedError(ConflictError):
    default_code = "TICKET_ALREADY_ADMITTED"
    default_message = "Ce billet a déjà été utilisé."


class ScannerNotAssignedError(PermissionBusinessError):
    default_code = "SCANNER_NOT_ASSIGNED"
    default_message = "Ce scanner n'est pas autorisé pour cet événement."


@transaction.atomic
def admit_ticket_from_qr(*, token: str, scanner_user_id: UUID) -> TicketAdmission:
    ticket_identity = parse_ticket_qr_identity(
        token=token,
    )
    if ticket_identity is None:
        raise InvalidTicketQrError()

    ticket_id, qr_version = ticket_identity
    ticket = lock_ticket_for_admission(
        ticket_id=ticket_id,
    )
    if ticket is None or ticket.qr_version != qr_version:
        raise InvalidTicketQrError()

    require_event_admission_open(
        event_id=ticket.event_id,
    )

    scanner_id = resolve_active_scanner_id(
        user_id=scanner_user_id,
    )
    if scanner_id is None or not is_scanner_assigned_to_event(
        scanner_id=scanner_id,
        event_id=ticket.event_id,
    ):
        raise ScannerNotAssignedError()

    if ticket.is_used:
        raise TicketAlreadyAdmittedError()

    if not ticket.is_valid:
        raise InvalidTicketQrError()

    admission = TicketAdmission.objects.create(
        ticket_id=ticket.id,
        scanner_id=scanner_id,
        admitted_at=timezone.now(),
    )

    mark_ticket_used(
        ticket_id=ticket.id,
    )

    return admission
