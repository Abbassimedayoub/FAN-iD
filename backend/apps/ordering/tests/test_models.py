from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.ordering.models import ORDER_PENDING, Order, OrderLine, StockHold


@pytest.fixture
def user(db, django_user_model, roles):
    credential = "testpassword123"

    return django_user_model.objects.create_user(
        email="buyer@example.test",
        password=credential,
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
    )


@pytest.fixture
def order(user):
    return Order.objects.create(
        user=user,
        total_amount_cents=2500,
    )


def test_order_is_created_with_pending_status(order):
    assert order.status == ORDER_PENDING
    assert order.total_amount_cents == 2500
    assert order.version == 1


def test_order_line_is_linked_to_order(order):
    line = OrderLine.objects.create(
        order=order,
        label="Ticket VIP",
        quantity=2,
        unit_price_cents=1250,
    )

    assert line.order_id == order.id
    assert order.lines.count() == 1


def test_stock_hold_is_linked_to_order(order):
    hold = StockHold.objects.create(
        order=order,
        expires_at=timezone.now() + datetime.timedelta(minutes=10),
    )

    assert hold.order_id == order.id
    assert hold.consumed is False


def test_order_line_quantity_constraint(order):
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        OrderLine.objects.create(
            order=order,
            label="Invalid",
            quantity=0,
            unit_price_cents=100,
        )


def test_order_has_multiple_lines(order):
    OrderLine.objects.create(
        order=order,
        label="A",
        quantity=1,
        unit_price_cents=100,
    )

    OrderLine.objects.create(
        order=order,
        label="B",
        quantity=3,
        unit_price_cents=200,
    )

    assert order.lines.count() == 2
