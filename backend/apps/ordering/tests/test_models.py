from __future__ import annotations

import datetime

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.catalog.models import Category, Event, TicketCategory
from apps.ordering.models import ORDER_PENDING, Order, OrderLine, StockHold, StockHoldLine


@pytest.fixture
def user(db, django_user_model, roles):
    return django_user_model.objects.create_user(
        email="buyer@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
    )


@pytest.fixture
def order(user):
    return Order.objects.create(
        user=user,
        total_amount_cents=2500,
    )


@pytest.fixture
def ticket_category(db):
    category = Category.objects.create(name="Ordering category")
    starts_at = timezone.now() + datetime.timedelta(days=7)

    event = Event.objects.create(
        category=category,
        name="Ordering event",
        starts_at=starts_at,
        ends_at=starts_at + datetime.timedelta(hours=2),
        capacity_total=100,
    )

    return TicketCategory.objects.create(
        event=event,
        name="Standard",
        quota=100,
        unit_price_cents=1250,
    )


def test_order_is_created_with_pending_status(order):
    assert order.status == ORDER_PENDING
    assert order.total_amount_cents == 2500
    assert order.version == 1


def test_order_line_is_linked_to_order_and_ticket_category(
    order,
    ticket_category,
):
    line = OrderLine.objects.create(
        order=order,
        ticket_category=ticket_category,
        label="Ticket VIP",
        quantity=2,
        unit_price_cents=1250,
    )

    assert line.order_id == order.id
    assert line.ticket_category_id == ticket_category.id
    assert order.lines.count() == 1


def test_stock_hold_is_linked_to_order(order):
    hold = StockHold.objects.create(
        order=order,
        expires_at=timezone.now() + datetime.timedelta(minutes=10),
    )

    assert hold.order_id == order.id
    assert hold.consumed is False


def test_stock_hold_line_is_linked_to_hold_and_ticket_category(
    order,
    ticket_category,
):
    hold = StockHold.objects.create(
        order=order,
        expires_at=timezone.now() + datetime.timedelta(minutes=10),
    )

    line = StockHoldLine.objects.create(
        stock_hold=hold,
        ticket_category=ticket_category,
        quantity=2,
    )

    assert line.stock_hold_id == hold.id
    assert line.ticket_category_id == ticket_category.id
    assert hold.lines.count() == 1


def test_order_line_quantity_constraint(order, ticket_category):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OrderLine.objects.create(
                order=order,
                ticket_category=ticket_category,
                label="Invalid",
                quantity=0,
                unit_price_cents=100,
            )


def test_stock_hold_line_quantity_constraint(order, ticket_category):
    hold = StockHold.objects.create(
        order=order,
        expires_at=timezone.now() + datetime.timedelta(minutes=10),
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StockHoldLine.objects.create(
                stock_hold=hold,
                ticket_category=ticket_category,
                quantity=0,
            )


def test_stock_hold_has_one_line_per_ticket_category(
    order,
    ticket_category,
):
    hold = StockHold.objects.create(
        order=order,
        expires_at=timezone.now() + datetime.timedelta(minutes=10),
    )

    StockHoldLine.objects.create(
        stock_hold=hold,
        ticket_category=ticket_category,
        quantity=1,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StockHoldLine.objects.create(
                stock_hold=hold,
                ticket_category=ticket_category,
                quantity=1,
            )
