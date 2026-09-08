from __future__ import annotations

import datetime

import pytest
from django.test import Client
from django.utils import timezone

from apps.catalog.models import Category, Event, TicketCategory
from apps.ordering.services.confirmation import confirm_order_payment
from apps.ordering.services.reservations import ReservationLine, reserve_stock
from apps.ticketing.models import TICKET_VALID, Ticket


@pytest.fixture
def buyer(db, django_user_model, roles):
    return django_user_model.objects.create_user(
        email="ticket-buyer@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


@pytest.fixture
def tariff():
    category = Category.objects.create(name="Ticketing category")
    starts_at = timezone.now() + datetime.timedelta(days=7)
    event = Event.objects.create(
        category=category,
        name="Ticketing event",
        status=Event.PUBLISHED,
        published_at=timezone.now(),
        starts_at=starts_at,
        ends_at=starts_at + datetime.timedelta(hours=2),
        capacity_total=20,
    )
    return TicketCategory.objects.create(
        event=event,
        name="Standard",
        quota=20,
        unit_price_cents=1200,
    )


def test_paid_order_issues_one_ticket_per_quantity(buyer, tariff):
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(tariff.id, 2)],
    )

    confirm_order_payment(order_id=order.id)

    tickets = list(
        Ticket.objects.filter(order_line__order=order).order_by("sequence")
    )

    assert [ticket.sequence for ticket in tickets] == [1, 2]
    assert all(ticket.user_id == buyer.id for ticket in tickets)
    assert all(ticket.event_id == tariff.event_id for ticket in tickets)
    assert all(ticket.ticket_category_id == tariff.id for ticket in tickets)
    assert all(ticket.status == TICKET_VALID for ticket in tickets)


def test_payment_confirmation_retry_does_not_duplicate_tickets(buyer, tariff):
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(tariff.id, 2)],
    )

    confirm_order_payment(order_id=order.id)
    confirm_order_payment(order_id=order.id)

    assert Ticket.objects.filter(order_line__order=order).count() == 2


def test_authenticated_user_reads_only_own_tickets(buyer, tariff, django_user_model, roles):
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(tariff.id, 1)],
    )
    confirm_order_payment(order_id=order.id)

    other_user = django_user_model.objects.create_user(
        email="other-ticket-buyer@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )

    client = Client()
    client.force_login(buyer)

    response = client.get("/api/v1/tickets")

    assert response.status_code == 200, response.content
    payload = response.json()

    assert len(payload["results"]) == 1
    assert payload["results"][0]["event_name"] == tariff.event.name
    assert payload["results"][0]["ticket_category_name"] == "Standard"

    client.force_login(other_user)
    assert client.get("/api/v1/tickets").json()["results"] == []


def test_ticket_listing_exposes_postponement_information(buyer, tariff):
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(tariff.id, 1)],
    )
    confirm_order_payment(order_id=order.id)

    event = tariff.event
    original_start = event.starts_at
    new_start = original_start + datetime.timedelta(days=14)

    event.status = Event.POSTPONED
    event.lifecycle_reason = "Report pour conditions météorologiques."
    event.postponed_from_starts_at = original_start
    event.postponed_from_ends_at = event.ends_at
    event.postponed_to_starts_at = new_start
    event.postponed_to_ends_at = new_start + datetime.timedelta(hours=2)
    event.save(
        update_fields=[
            "status",
            "lifecycle_reason",
            "postponed_from_starts_at",
            "postponed_from_ends_at",
            "postponed_to_starts_at",
            "postponed_to_ends_at",
        ]
    )

    client = Client()
    client.force_login(buyer)

    ticket = client.get("/api/v1/tickets").json()["results"][0]

    assert ticket["status"] == TICKET_VALID
    assert ticket["event_status"] == Event.POSTPONED
    assert ticket["postponement_reason"] == event.lifecycle_reason
    assert ticket["postponed_from_starts_at"] is not None
    assert ticket["postponed_to_starts_at"] is not None
