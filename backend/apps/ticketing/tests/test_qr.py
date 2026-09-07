from datetime import datetime, timezone

import jwt
import pytest
from django.test import override_settings

from apps.ticketing.models import TICKET_USED, Ticket
from apps.ticketing.services.qr import (
    QR_ISSUER,
    QR_TYPE,
    TicketQrUnavailableError,
    issue_dynamic_ticket_qr,
)


@override_settings(QR_SIGNING_KEY="test-qr-signing-key-which-is-long-enough")
def test_dynamic_qr_is_signed_and_expires_in_30_seconds():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ticket = Ticket()

    qr = issue_dynamic_ticket_qr(ticket=ticket, now=now)

    claims = jwt.decode(
        qr.token,
        "test-qr-signing-key-which-is-long-enough",
        algorithms=["HS256"],
        issuer=QR_ISSUER,
        options={"verify_exp": False},
    )

    assert claims["typ"] == QR_TYPE
    assert claims["tid"] == str(ticket.id)
    assert claims["exp"] == int(qr.expires_at.timestamp())
    assert qr.expires_at == datetime(2026, 1, 1, 12, 0, 30, tzinfo=timezone.utc)


@override_settings(QR_SIGNING_KEY="test-qr-signing-key-which-is-long-enough")
def test_used_ticket_cannot_generate_dynamic_qr():
    ticket = Ticket(status=TICKET_USED)

    with pytest.raises(TicketQrUnavailableError):
        issue_dynamic_ticket_qr(ticket=ticket)
