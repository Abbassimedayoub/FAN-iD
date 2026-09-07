from __future__ import annotations

import datetime

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from apps.access.models import ScannerPresence, TicketAdmission
from apps.access.services.admission_sessions import (
    EventAdmissionClosedError,
    close_event_admission,
    open_event_admission,
)
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
def organizer(buyer):
    return Organizer.objects.create(
        user=buyer,
        org_name="Admission organization",
        contact_email="admission-org@example.test",
    )


@pytest.fixture
def ticket(buyer, organizer):
    category = Category.objects.create(name="Admission category")
    starts_at = timezone.now() + datetime.timedelta(days=7)
    event = Event.objects.create(
        category=category,
        organizer=organizer,
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
def scanner(organizer, buyer, django_user_model, roles):
    scanner_user = django_user_model.objects.create_user(
        email="admission-scanner@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["SCANNER"],
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

    with pytest.raises(EventAdmissionClosedError):
        admit_ticket_from_qr(
            token=token,
            scanner_user_id=scanner.user_id,
        )

    open_event_admission(
        event_id=ticket.event_id,
        opened_by_id=buyer.id,
    )

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
    organizer_client = Client()
    organizer_client.force_login(buyer)

    response = organizer_client.post(
        f"/api/v1/access/events/{ticket.event_id}/admission/open",
    )
    assert response.status_code == 200, response.content
    assert response.json()["is_open"] is True

    client = Client()
    client.force_login(scanner.user)

    response = client.post(
        "/api/v1/access/scans",
        data={"token": issue_dynamic_ticket_qr(ticket=ticket).token},
        content_type="application/json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["status"] == "ADMITTED"


def test_admission_session_reopens_only_after_closure(ticket, buyer):
    first = open_event_admission(
        event_id=ticket.event_id,
        opened_by_id=buyer.id,
    )
    second = open_event_admission(
        event_id=ticket.event_id,
        opened_by_id=buyer.id,
    )

    assert first.id == second.id

    closed = close_event_admission(
        event_id=ticket.event_id,
        closed_by_id=buyer.id,
    )

    assert closed is not None
    assert closed.closed_at is not None
    assert closed.closed_by_id == buyer.id


def test_owner_reads_event_live_dashboard(ticket, buyer):
    client = Client()
    client.force_login(buyer)

    response = client.get(
        f"/api/v1/access/events/{ticket.event_id}/live-dashboard",
    )

    assert response.status_code == 200, response.content
    payload = response.json()

    assert payload["event_id"] == str(ticket.event_id)
    assert payload["ticketing"]["sold_count"] == 1
    assert payload["ticketing"]["remaining_count"] == 19
    assert payload["capacity"]["entries_count"] == 0
    assert payload["admission"]["is_open"] is False


def test_scanner_heartbeat_marks_presence_in_dashboard(ticket, scanner, buyer):
    EventScannerAssignment.objects.create(
        event=ticket.event,
        scanner_id=scanner.id,
        assigned_by_id=buyer.id,
    )

    scanner_client = Client()
    scanner_client.force_login(scanner.user)
    heartbeat = scanner_client.post("/api/v1/access/scanners/heartbeat")

    assert heartbeat.status_code == 200, heartbeat.content
    assert ScannerPresence.objects.filter(scanner=scanner).exists()

    organizer_client = Client()
    organizer_client.force_login(buyer)
    dashboard = organizer_client.get(
        f"/api/v1/access/events/{ticket.event_id}/live-dashboard",
    )

    assert dashboard.status_code == 200, dashboard.content
    assert dashboard.json()["scanners"]["present_count"] == 1
    assert dashboard.json()["scanners"]["items"][0]["is_present"] is True
