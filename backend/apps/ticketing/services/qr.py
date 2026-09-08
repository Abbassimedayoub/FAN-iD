from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from apps.core.exceptions import ConflictError

from ..models import TICKET_VALID, Ticket


QR_TTL_SECONDS = 30
QR_ISSUER = "fanid-ticketing"
QR_TYPE = "fanid.ticket_qr.v1"


class TicketQrUnavailableError(ConflictError):
    default_code = "TICKET_QR_UNAVAILABLE"
    default_message = "Ce billet ne peut pas générer de QR code."


@dataclass(frozen=True)
class DynamicTicketQr:
    token: str
    expires_at: datetime


def issue_dynamic_ticket_qr(
    *,
    ticket: Ticket,
    now: datetime | None = None,
) -> DynamicTicketQr:
    """Génère un QR signé, renouvelable et valable 30 secondes."""
    if ticket.status != TICKET_VALID:
        raise TicketQrUnavailableError(
            details={
                "ticket_id": str(ticket.id),
                "status": ticket.status,
            }
        )

    signing_key = settings.QR_SIGNING_KEY.strip()
    if not signing_key:
        raise ImproperlyConfigured("QR_SIGNING_KEY must be configured.")

    moment = now or timezone.now()
    expires_at = moment + timedelta(seconds=QR_TTL_SECONDS)

    payload = {
        "typ": QR_TYPE,
        "iss": QR_ISSUER,
        "tid": str(ticket.id),
        "qv": ticket.qr_version,
        "iat": int(moment.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_urlsafe(16),
    }

    return DynamicTicketQr(
        token=jwt.encode(payload, signing_key, algorithm="HS256"),
        expires_at=expires_at,
    )
