from __future__ import annotations

import datetime

import jwt

import pytest
from django.utils import timezone

from apps.access.services.admission_sessions import open_event_admission
from apps.access.services.admissions import (
    TicketAlreadyAdmittedError,
    admit_ticket_from_qr,
)
from apps.access.services.final_reports import build_event_final_report
from apps.catalog.models import (
    Category,
    Event,
    EventScannerAssignment,
    TicketCategory,
)
from apps.catalog.services.completion import complete_elapsed_events
from apps.core.adapters.payments import FakeGateway
from apps.ordering.services.reservations import ReservationLine, reserve_stock
from apps.organizing.constants import SCANNER_ACTIVE
from apps.organizing.models import Organizer, Scanner
from apps.payments.services import (
    create_payment_intent,
    execute_payment_refund,
    mark_payment_intent_succeeded,
    request_event_refunds,
)
from apps.ticketing.models import TICKET_USED, TICKET_VALID, TICKET_VOID, Ticket
from apps.ticketing.services.qr import issue_dynamic_ticket_qr


@pytest.fixture
def release_context(django_user_model, roles):
    now = timezone.now()
    owner = django_user_model.objects.create_user(
        email="release-organizer@example.test",
        password="testpassword123",
        first_name="Amina",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=now,
        role=roles["FAN"],
    )
    organizer = Organizer.objects.create(
        user=owner,
        org_name="Release Organizer",
        contact_email="release-organizer@example.test",
    )
    buyer = django_user_model.objects.create_user(
        email="release-buyer@example.test",
        password="testpassword123",
        first_name="Samir",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=now,
        role=roles["FAN"],
    )
    scanner_user = django_user_model.objects.create_user(
        email="release-scanner@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=now,
        role=roles["SCANNER"],
    )
    scanner = Scanner.objects.create(
        organizer=organizer,
        user=scanner_user,
        invited_by=owner,
        status=SCANNER_ACTIVE,
    )
    return {
        "buyer": buyer,
        "owner": owner,
        "organizer": organizer,
        "scanner": scanner,
    }


def _paid_event_with_tickets(*, context, quantity: int) -> tuple[Event, list[Ticket]]:
    starts_at = timezone.now() + datetime.timedelta(days=7)
    category = Category.objects.create(name=f"Release category {quantity}")
    event = Event.objects.create(
        organizer=context["organizer"],
        category=category,
        name="Release journey event",
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
        user=context["buyer"],
        lines=[ReservationLine(tariff.id, quantity)],
    )
    gateway = FakeGateway()
    intent = create_payment_intent(
        order_id=order.id,
        user=context["buyer"],
        gateway=gateway,
    )
    mark_payment_intent_succeeded(
        provider_intent_id=intent.provider_intent_id,
    )
    tickets = list(
        Ticket.objects.filter(order_line__order=order).order_by("sequence")
    )
    return event, tickets


@pytest.mark.django_db
def test_release_journey_sale_scan_double_scan_and_final_report(
    release_context,
):
    """
    Parcours principal : vente payée, émission, ouverture, scan, double scan,
    fin automatique et statistiques finales.
    """
    event, tickets = _paid_event_with_tickets(
        context=release_context,
        quantity=2,
    )
    scanner = release_context["scanner"]

    EventScannerAssignment.objects.create(
        event=event,
        scanner_id=scanner.id,
        assigned_by_id=release_context["owner"].id,
    )
    qr_token = issue_dynamic_ticket_qr(ticket=tickets[0]).token

    open_event_admission(
        event_id=event.id,
        opened_by_id=release_context["owner"].id,
    )
    admission = admit_ticket_from_qr(
        token=qr_token,
        scanner_user_id=scanner.user_id,
    )
    assert admission.ticket_id == tickets[0].id

    with pytest.raises(TicketAlreadyAdmittedError):
        admit_ticket_from_qr(
            token=qr_token,
            scanner_user_id=scanner.user_id,
        )

    tickets[0].refresh_from_db()
    tickets[1].refresh_from_db()
    assert tickets[0].status == TICKET_USED
    assert tickets[1].status == TICKET_VALID

    now = timezone.now()
    event.starts_at = now - datetime.timedelta(hours=3)
    event.ends_at = now - datetime.timedelta(minutes=1)
    event.save(update_fields=["starts_at", "ends_at"])

    assert complete_elapsed_events(now=now) == 1

    event.refresh_from_db()
    report = build_event_final_report(event_id=event.id)

    assert event.status == Event.COMPLETED
    assert report.tickets_sold_count == 2
    assert report.tickets_used_count == 1
    assert report.tickets_absent_count == 1
    assert report.tickets_voided_count == 0
    assert report.gross_revenue_cents == 2400
    assert report.refunds_cents == 0
    assert report.organizer_net_cents + report.commission_cents == 2400


@pytest.mark.django_db
def test_release_journey_postponement_preserves_paid_ticket_and_qr(
    release_context,
):
    """Un report garde les billets vendus et ne rend pas le QR inutilisable."""
    event, tickets = _paid_event_with_tickets(
        context=release_context,
        quantity=1,
    )
    ticket = tickets[0]
    previous_token = issue_dynamic_ticket_qr(ticket=ticket).token
    new_start = event.starts_at + datetime.timedelta(days=14)

    event.status = Event.POSTPONED
    event.postponed_from_starts_at = event.starts_at
    event.postponed_from_ends_at = event.ends_at
    event.postponed_to_starts_at = new_start
    event.postponed_to_ends_at = new_start + datetime.timedelta(hours=2)
    event.starts_at = new_start
    event.ends_at = new_start + datetime.timedelta(hours=2)
    event.save(
        update_fields=[
            "status",
            "postponed_from_starts_at",
            "postponed_from_ends_at",
            "postponed_to_starts_at",
            "postponed_to_ends_at",
            "starts_at",
            "ends_at",
        ]
    )

    ticket.refresh_from_db()

    current_token = issue_dynamic_ticket_qr(ticket=ticket).token
    previous_claims = jwt.decode(
        previous_token,
        options={"verify_signature": False},
    )
    current_claims = jwt.decode(
        current_token,
        options={"verify_signature": False},
    )

    assert event.status == Event.POSTPONED
    assert ticket.status == TICKET_VALID
    # Chaque QR dynamique a un jti neuf et est donc différent à chaque appel.
    # En revanche, le report ne change pas qv : le QR déjà émis reste accepté
    # jusqu’à son expiration normale.
    assert previous_claims["qv"] == current_claims["qv"] == ticket.qr_version


@pytest.mark.django_db
def test_release_journey_cancellation_refunds_and_voids_paid_tickets(
    release_context,
):
    """
    La phase remboursement est exécutée avec FakeGateway : aucune interaction
    Stripe réelle, mais mêmes montants, idempotence et invalidation billet.
    """
    event, tickets = _paid_event_with_tickets(
        context=release_context,
        quantity=2,
    )
    event.status = Event.CANCELLED
    event.lifecycle_reason = "Annulation test de release."
    event.save(update_fields=["status", "lifecycle_reason"])

    refunds = request_event_refunds(event_id=event.id)
    assert len(refunds) == 1
    assert refunds[0].amount_cents == 2400

    completed = execute_payment_refund(
        refund_id=refunds[0].id,
        gateway=FakeGateway(),
    )
    repeated = execute_payment_refund(
        refund_id=refunds[0].id,
        gateway=FakeGateway(),
    )

    for ticket in tickets:
        ticket.refresh_from_db()

    assert completed.id == repeated.id
    assert completed.status == "SUCCEEDED"
    assert all(ticket.status == TICKET_VOID for ticket in tickets)
