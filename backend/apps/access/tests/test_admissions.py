from __future__ import annotations

import datetime

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from apps.access.models import TicketAdmission
from apps.access.services.admissions import (
    TicketAlreadyAdmittedError,
    admit_ticket_from_qr,
)
from apps.catalog.models import (
    Category,
    Event,
    EventScannerAssignment,
    TicketCategory,
)
from apps.ordering.services.confirmation import confirm_order_payment
from apps.ordering.services.reservations import ReservationLine, reserve_stock
from apps.organizing.constants import SCANNER_ACTIVE
from apps.organizing.models import Organizer, Scanner
from apps.ticketing.models import TICKET_USED, Ticket
from apps.ticketing.services.qr import issue_dynamic_ticket_qr


@pytest.fixture
def buyer(db, django_user_model, roles):
    return django_user_model.objects.create_user(
        email="admission-buyer@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


@pytest.fixture
def ticket(buyer):
    category = Category.objects.create(name="Admission category")
    starts_at = timezone.now() + datetime.timedelta(days=7)
    event = Event.objects.create(
        category=category,
        name="Admission event",
        status=Event.PUBLISHED,
        published_at=timezone.now(),
        starts_at=starts_at,
        ends_at=starts_at + datetime.timedelta(hours=2),
        capacity_total=20,
    )
    tariff = TicketCategory.objects.create(
        event=event,
        name="Standard",
        quota=20,
        unit_price_cents=1200,
    )
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(tariff.id, 1)],
    )
    confirm_order_payment(order_id=order.id)
    return Ticket.objects.get(order_line__order=order)


@pytest.fixture
def scanner(buyer, django_user_model, roles):
    scanner_user = django_user_model.objects.create_user(
        email="admission-scanner@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["SCANNER"],
    )
    organizer = Organizer.objects.create(
        user=buyer,
        org_name="Admission organization",
        contact_email="admission-org@example.test",
    )
    return Scanner.objects.create(
        organizer=organizer,
        user=scanner_user,
        invited_by=buyer,
        status=SCANNER_ACTIVE,
    )


@override_settings(QR_SIGNING_KEY="test-qr-signing-key-which-is-long-enough")
def test_scanner_admits_ticket_once(ticket, scanner, buyer):
    EventScannerAssignment.objects.create(
        event=ticket.event,
        scanner_id=scanner.id,
        assigned_by_id=buyer.id,
    )
    token = issue_dynamic_ticket_qr(ticket=ticket).token

    admission = admit_ticket_from_qr(
        token=token,
        scanner_user_id=scanner.user_id,
    )

    ticket.refresh_from_db()
    assert admission.ticket_id == ticket.id
    assert admission.scanner_id == scanner.id
    assert ticket.status == TICKET_USED
    assert TicketAdmission.objects.count() == 1

    with pytest.raises(TicketAlreadyAdmittedError):
        admit_ticket_from_qr(
            token=token,
            scanner_user_id=scanner.user_id,
        )


@override_settings(QR_SIGNING_KEY="test-qr-signing-key-which-is-long-enough")
def test_scan_endpoint_returns_admitted(ticket, scanner, buyer):
    EventScannerAssignment.objects.create(
        event=ticket.event,
        scanner_id=scanner.id,
        assigned_by_id=buyer.id,
    )
    client = Client()
    client.force_login(scanner.user)

    response = client.post(
        "/api/v1/access/scans",
        data={"token": issue_dynamic_ticket_qr(ticket=ticket).token},
        content_type="application/json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["status"] == "ADMITTED"
