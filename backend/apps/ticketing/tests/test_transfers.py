from __future__ import annotations

import datetime

import jwt
import pytest
from django.test import Client, override_settings
from django.utils import timezone

from apps.catalog.models import Category, Event, TicketCategory
from apps.core.exceptions import ConflictError
from apps.ordering.services.confirmation import confirm_order_payment
from apps.ordering.services.reservations import ReservationLine, reserve_stock
from apps.ticketing.models import Ticket, TicketTransferAudit
from apps.ticketing.services.qr import QR_ISSUER, issue_dynamic_ticket_qr
from apps.ticketing.services.transfers import transfer_ticket


@pytest.fixture
def transfer_setup(django_user_model, roles):
    now = timezone.now()
    owner = django_user_model.objects.create_user(
        email="transfer-owner@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=now,
        role=roles["FAN"],
    )
    recipient = django_user_model.objects.create_user(
        email="transfer-recipient@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=now,
        role=roles["FAN"],
    )
    category = Category.objects.create(name="Transfer category")
    starts_at = now + datetime.timedelta(days=2)
    event = Event.objects.create(
        category=category,
        name="Transfer event",
        status=Event.PUBLISHED,
        published_at=now,
        starts_at=starts_at,
        ends_at=starts_at + datetime.timedelta(hours=2),
        capacity_total=2,
    )
    tariff = TicketCategory.objects.create(
        event=event,
        name="Transfer standard",
        quota=2,
        unit_price_cents=1200,
    )
    order = reserve_stock(
        user=owner,
        lines=[ReservationLine(tariff.id, 1)],
    )
    confirm_order_payment(order_id=order.id)
    ticket = Ticket.objects.get(order_line__order=order)
    return owner, recipient, ticket


@pytest.mark.django_db
def test_transfer_moves_owner_audits_and_rotates_qr_version(transfer_setup):
    owner, recipient, ticket = transfer_setup

    transferred = transfer_ticket(
        ticket_id=ticket.id,
        owner_user_id=owner.id,
        recipient_email=recipient.email.upper(),
    )

    transferred.refresh_from_db()
    assert transferred.user_id == recipient.id
    assert transferred.qr_version == 2

    audit = TicketTransferAudit.objects.get(ticket=transferred)
    assert audit.previous_user_id == owner.id
    assert audit.recipient_user_id == recipient.id


@pytest.mark.django_db
@override_settings(QR_SIGNING_KEY="test-qr-signing-key-which-is-long-enough")
def test_transfer_invalidates_previously_issued_qr(transfer_setup):
    owner, recipient, ticket = transfer_setup
    old_qr = issue_dynamic_ticket_qr(ticket=ticket)

    transfer_ticket(
        ticket_id=ticket.id,
        owner_user_id=owner.id,
        recipient_email=recipient.email,
    )
    ticket.refresh_from_db()

    old_claims = jwt.decode(
        old_qr.token,
        "test-qr-signing-key-which-is-long-enough",
        algorithms=["HS256"],
        issuer=QR_ISSUER,
        options={"verify_exp": False},
    )
    assert old_claims["qv"] != ticket.qr_version


@pytest.mark.django_db
def test_owner_can_transfer_ticket_via_api(transfer_setup):
    owner, recipient, ticket = transfer_setup
    client = Client()
    client.force_login(owner)

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/transfer",
        data={"recipient_email": recipient.email},
        content_type="application/json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["ticket"]["id"] == str(ticket.id)

    ticket.refresh_from_db()
    assert ticket.user_id == recipient.id


@pytest.mark.django_db
def test_transfer_is_blocked_at_event_start(transfer_setup):
    owner, recipient, ticket = transfer_setup
    ticket.event.starts_at = timezone.now() - datetime.timedelta(seconds=1)
    ticket.event.save(update_fields=["starts_at"])

    with pytest.raises(ConflictError):
        transfer_ticket(
            ticket_id=ticket.id,
            owner_user_id=owner.id,
            recipient_email=recipient.email,
        )


@pytest.mark.django_db
def test_transfer_email_notifies_previous_owner_and_recipient(
    transfer_setup,
    monkeypatch,
):
    from apps.notifying.ticket_transfer_tasks import (
        send_ticket_transfer_emails,
    )

    owner, recipient, ticket = transfer_setup

    transfer_ticket(
        ticket_id=ticket.id,
        owner_user_id=owner.id,
        recipient_email=recipient.email,
    )
    audit = TicketTransferAudit.objects.get(ticket=ticket)

    class FakeSender:
        def __init__(self):
            self.emails_sent = []

        def send_email(self, **kwargs):
            self.emails_sent.append(kwargs)

    sender = FakeSender()
    monkeypatch.setattr(
        "apps.notifying.ticket_transfer_tasks.build_notification_sender",
        lambda: sender,
    )

    result = send_ticket_transfer_emails.run(
        transfer_audit_id=str(audit.id),
    )

    assert result == {"sent": True, "recipients": 2}
    assert [email["to"] for email in sender.emails_sent] == [
        owner.email,
        recipient.email,
    ]
    assert "invalide" in sender.emails_sent[0]["body"]
    assert "Mes billets" in sender.emails_sent[1]["body"]
