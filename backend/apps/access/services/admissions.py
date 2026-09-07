from __future__ import annotations

from uuid import UUID

import jwt
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import (
    ConflictError,
    PermissionBusinessError,
    ValidationBusinessError,
)
from apps.organizing.api import resolve_active_scanner_event_assignment
from apps.ticketing.models import TICKET_VALID, TICKET_USED, Ticket
from apps.ticketing.services.qr import QR_ISSUER, QR_TYPE

from .admission_sessions import require_event_admission_open

from ..models import TicketAdmission


class InvalidTicketQrError(ValidationBusinessError):
    default_code = "INVALID_TICKET_QR"
    default_message = "Le QR présenté est invalide ou expiré."


class TicketAlreadyAdmittedError(ConflictError):
    default_code = "TICKET_ALREADY_ADMITTED"
    default_message = "Ce billet a déjà été utilisé."


class ScannerNotAssignedError(PermissionBusinessError):
    default_code = "SCANNER_NOT_ASSIGNED"
    default_message = "Ce scanner n'est pas autorisé pour cet événement."


def _ticket_id_from_qr(token: str) -> UUID:
    try:
        claims = jwt.decode(
            token,
            settings.QR_SIGNING_KEY,
            algorithms=["HS256"],
            issuer=QR_ISSUER,
        )
        if claims.get("typ") != QR_TYPE:
            raise InvalidTicketQrError()

        return UUID(str(claims["tid"]))
    except InvalidTicketQrError:
        raise
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidTicketQrError() from exc


@transaction.atomic
def admit_ticket_from_qr(*, token: str, scanner_user_id: UUID) -> TicketAdmission:
    ticket_id = _ticket_id_from_qr(token)

    try:
        ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
    except Ticket.DoesNotExist as exc:
        raise InvalidTicketQrError() from exc

    require_event_admission_open(event_id=ticket.event_id)

    scanner_id = resolve_active_scanner_event_assignment(
        user_id=scanner_user_id,
        event_id=ticket.event_id,
    )
    if scanner_id is None:
        raise ScannerNotAssignedError()

    if ticket.status == TICKET_USED:
        raise TicketAlreadyAdmittedError()

    if ticket.status != TICKET_VALID:
        raise InvalidTicketQrError()

    admission = TicketAdmission.objects.create(
        ticket=ticket,
        scanner_id=scanner_id,
        admitted_at=timezone.now(),
    )

    ticket.status = TICKET_USED
    ticket.save(update_fields=["status"])

    return admission
