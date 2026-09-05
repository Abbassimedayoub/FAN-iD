from __future__ import annotations

import datetime
from datetime import timedelta
import json
import threading

import pytest
from django.db import connections
from django.test import Client
from django.utils import timezone

from apps.catalog.models import Category, Event, TicketCategory
from apps.core.idempotency.middleware import REPLAYED_MARKER_HEADER
from apps.ordering.models import Order, StockHoldLine
from apps.ordering.services.reservations import (
    ReservationLine,
    SaleUnavailableError,
    StockUnavailableError,
    reserve_stock,
)


@pytest.fixture
def buyer(db, django_user_model, roles):
    return django_user_model.objects.create_user(
        email="reservation@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
    )


@pytest.fixture
def tariffs(db):
    category = Category.objects.create(name="Reservation category")
    start = timezone.now() + datetime.timedelta(days=7)
    event = Event.objects.create(
        category=category,
        name="Reservation event",
        status=Event.PUBLISHED,
        published_at=timezone.now(),
        starts_at=start,
        ends_at=start + datetime.timedelta(hours=2),
        capacity_total=5,
    )
    return (
        TicketCategory.objects.create(
            event=event, name="Standard", quota=5, unit_price_cents=1200,
        ),
        TicketCategory.objects.create(
            event=event, name="VIP", quota=5, unit_price_cents=2500,
        ),
    )


@pytest.mark.django_db
def test_reserve_stock_creates_order_lines_and_hold(buyer, tariffs):
    standard, _ = tariffs

    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(standard.id, 2)],
    )

    assert order.total_amount_cents == 2400
    assert order.lines.get().ticket_category_id == standard.id
    assert order.lines.get().quantity == 2
    assert order.stock_hold.lines.get().quantity == 2


@pytest.mark.django_db
def test_active_hold_prevents_oversell(buyer, tariffs):
    standard, _ = tariffs
    reserve_stock(user=buyer, lines=[ReservationLine(standard.id, 3)])

    with pytest.raises(StockUnavailableError):
        reserve_stock(user=buyer, lines=[ReservationLine(standard.id, 3)])

    assert Order.objects.count() == 1
    assert StockHoldLine.objects.count() == 1


@pytest.mark.django_db
def test_expired_hold_no_longer_blocks_stock(buyer, tariffs):
    standard, _ = tariffs
    first = reserve_stock(user=buyer, lines=[ReservationLine(standard.id, 3)])
    first.stock_hold.expires_at = timezone.now() - datetime.timedelta(seconds=1)
    first.stock_hold.save(update_fields=["expires_at"])

    second = reserve_stock(user=buyer, lines=[ReservationLine(standard.id, 3)])

    assert second.lines.get().quantity == 3


@pytest.mark.django_db
def test_event_capacity_covers_multiple_tariffs(buyer, tariffs):
    standard, vip = tariffs
    reserve_stock(user=buyer, lines=[ReservationLine(standard.id, 3)])

    with pytest.raises(StockUnavailableError):
        reserve_stock(user=buyer, lines=[ReservationLine(vip.id, 3)])


@pytest.mark.django_db
def test_closed_sale_is_rejected(buyer, tariffs):
    standard, _ = tariffs
    standard.event.sales_ends_at = timezone.now() - datetime.timedelta(seconds=1)
    standard.event.save(update_fields=["sales_ends_at"])

    with pytest.raises(SaleUnavailableError):
        reserve_stock(user=buyer, lines=[ReservationLine(standard.id, 1)])


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_reservations_do_not_oversell(
    buyer,
    tariffs,
):
    standard, _ = tariffs
    barrier = threading.Barrier(2)
    results = []
    results_lock = threading.Lock()

    def worker() -> None:
        connections.close_all()

        try:
            barrier.wait()

            order = reserve_stock(
                user=buyer,
                lines=[ReservationLine(standard.id, 3)],
            )
            outcome = ("success", order.id)
        except StockUnavailableError:
            outcome = ("unavailable", None)
        finally:
            connections.close_all()

        with results_lock:
            results.append(outcome)

    threads = [
        threading.Thread(target=worker),
        threading.Thread(target=worker),
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert len(results) == 2, results
    assert sorted(kind for kind, _ in results) == [
        "success",
        "unavailable",
    ], results
    assert Order.objects.count() == 1
    assert StockHoldLine.objects.get().quantity == 3


RESERVATION_URL = "/api/v1/orders/reservations"


def test_reservation_endpoint_creates_order_and_hold(buyer, tariffs):
    standard, _ = tariffs
    client = Client()
    client.force_login(buyer)

    response = client.post(
        RESERVATION_URL,
        data=json.dumps(
            {
                "items": [
                    {
                        "ticket_category_id": str(standard.pk),
                        "quantity": 2,
                    },
                ],
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 201, response.content
    payload = response.json()

    assert payload["status"] == "PENDING"
    assert payload["total_amount_cents"] == standard.unit_price_cents * 2
    assert payload["lines"] == [
        {
            "ticket_category_id": str(standard.pk),
            "label": standard.name,
            "quantity": 2,
            "unit_price_cents": standard.unit_price_cents,
        },
    ]
    assert payload["hold_expires_at"]

    order = Order.objects.get(pk=payload["order_id"])
    assert order.user == buyer
    assert StockHoldLine.objects.get(
        stock_hold__order=order,
        ticket_category=standard,
    ).quantity == 2


def test_reservation_endpoint_replays_same_idempotency_key(buyer, tariffs):
    standard, _ = tariffs
    client = Client()
    client.force_login(buyer)

    body = {
        "items": [
            {
                "ticket_category_id": str(standard.pk),
                "quantity": 2,
            },
        ],
    }

    first = client.post(
        RESERVATION_URL,
        data=json.dumps(body),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="reservation-replay-key",
    )
    replay = client.post(
        RESERVATION_URL,
        data=json.dumps(body),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="reservation-replay-key",
    )

    assert first.status_code == 201, first.content
    assert replay.status_code == 201, replay.content
    assert replay.headers.get(REPLAYED_MARKER_HEADER) == "true"
    assert replay.json() == first.json()
    assert Order.objects.filter(user=buyer).count() == 1
    assert StockHoldLine.objects.filter(
        stock_hold__order__user=buyer,
        ticket_category=standard,
    ).count() == 1


from apps.ordering.services.confirmation import (
    ReservationExpiredError,
    confirm_order_payment,
)


def test_paid_confirmation_consumes_hold_and_increments_stock(buyer, tariffs):
    standard, _ = tariffs
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(standard.id, 2)],
    )

    confirmed = confirm_order_payment(order_id=order.id)

    order.refresh_from_db()
    order.stock_hold.refresh_from_db()
    standard.refresh_from_db()

    assert confirmed.id == order.id
    assert order.status == "PAID"
    assert order.stock_hold.consumed is True
    assert standard.sold_count == 2


def test_paid_confirmation_is_idempotent_and_never_double_counts_stock(
    buyer,
    tariffs,
):
    standard, _ = tariffs
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(standard.id, 2)],
    )

    first = confirm_order_payment(order_id=order.id)
    second = confirm_order_payment(order_id=order.id)

    standard.refresh_from_db()

    assert first.id == second.id == order.id
    assert standard.sold_count == 2


def test_paid_confirmation_rejects_an_expired_hold(buyer, tariffs):
    standard, _ = tariffs
    reserved_at = timezone.now()
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(standard.id, 1)],
        now=reserved_at,
    )

    with pytest.raises(ReservationExpiredError):
        confirm_order_payment(
            order_id=order.id,
            now=reserved_at + timedelta(minutes=11),
        )

    order.refresh_from_db()
    order.stock_hold.refresh_from_db()
    standard.refresh_from_db()

    assert order.status == "PENDING"
    assert order.stock_hold.consumed is False
    assert standard.sold_count == 0


def test_order_status_endpoint_returns_owned_order(buyer, tariffs):
    standard, _ = tariffs
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(standard.id, 2)],
    )

    client = Client()
    client.force_login(buyer)

    response = client.get(f"/api/v1/orders/{order.id}")

    assert response.status_code == 200, response.content
    assert response.json() == {
        "order_id": str(order.id),
        "status": "PENDING",
        "total_amount_cents": standard.unit_price_cents * 2,
        "hold_expires_at": order.stock_hold.expires_at.isoformat().replace(
            "+00:00",
            "Z",
        ),
    }


def test_order_status_endpoint_requires_authentication(buyer, tariffs):
    standard, _ = tariffs
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(standard.id, 1)],
    )

    response = Client().get(f"/api/v1/orders/{order.id}")

    assert response.status_code == 401
