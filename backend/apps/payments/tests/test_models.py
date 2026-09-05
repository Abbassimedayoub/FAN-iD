from __future__ import annotations

import datetime
import json

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from apps.core.adapters.payments import FakeGateway
from apps.ordering.models import Order, StockHold
from apps.ordering.services.confirmation import ReservationExpiredError
from apps.payments.models import PaymentIntent
from apps.payments.services import create_payment_intent


@pytest.fixture
def buyer(db, django_user_model, roles):
    return django_user_model.objects.create_user(
        email="payment-buyer@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


@pytest.fixture
def order(buyer):
    order = Order.objects.create(
        user=buyer,
        total_amount_cents=2400,
    )
    StockHold.objects.create(
        order=order,
        expires_at=timezone.now() + datetime.timedelta(minutes=10),
    )
    return order


def test_payment_intent_is_linked_to_order(order):
    intent = PaymentIntent.objects.create(
        order=order,
        provider="fake",
        provider_intent_id="pi_fake_payment_model",
        amount_cents=2400,
        client_secret="secret_payment_model",
    )

    assert intent.order_id == order.id
    assert intent.status == "CREATED"
    assert order.payment_intents.get() == intent


def test_provider_intent_id_is_unique(order):
    PaymentIntent.objects.create(
        order=order,
        provider="fake",
        provider_intent_id="pi_fake_unique",
        amount_cents=2400,
        client_secret="secret_one",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PaymentIntent.objects.create(
                order=order,
                provider="fake",
                provider_intent_id="pi_fake_unique",
                amount_cents=2400,
                client_secret="secret_two",
            )


def test_payment_intent_amount_must_be_positive(order):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PaymentIntent.objects.create(
                order=order,
                provider="fake",
                provider_intent_id="pi_fake_invalid_amount",
                amount_cents=0,
                client_secret="secret_invalid",
            )


def test_payment_intent_service_creates_gateway_intent(order, buyer):
    gateway = FakeGateway()

    intent = create_payment_intent(
        order_id=order.id,
        user=buyer,
        gateway=gateway,
    )

    assert intent.order_id == order.id
    assert intent.provider == "fake"
    assert intent.amount_cents == 2400
    assert intent.currency == "EUR"
    assert intent.client_secret.startswith("secret_")
    assert len(gateway.created_intents) == 1
    assert gateway.created_intents[0]["metadata"] == {
        "order_id": str(order.id),
        "user_id": str(buyer.id),
    }


def test_payment_intent_service_reuses_active_intent(order, buyer):
    gateway = FakeGateway()

    first = create_payment_intent(
        order_id=order.id,
        user=buyer,
        gateway=gateway,
    )
    second = create_payment_intent(
        order_id=order.id,
        user=buyer,
        gateway=gateway,
    )

    assert first.id == second.id
    assert PaymentIntent.objects.filter(order=order).count() == 1
    assert len(gateway.created_intents) == 1


def test_payment_intent_service_rejects_expired_reservation(order, buyer):
    gateway = FakeGateway()
    order.stock_hold.expires_at = timezone.now() - datetime.timedelta(seconds=1)
    order.stock_hold.save(update_fields=["expires_at"])

    with pytest.raises(ReservationExpiredError):
        create_payment_intent(
            order_id=order.id,
            user=buyer,
            gateway=gateway,
        )

    assert gateway.created_intents == []


def test_payment_intent_endpoint_returns_client_payment_data(order, buyer):
    client = Client()
    client.force_login(buyer)

    response = client.post(
        f"/api/v1/orders/{order.id}/payment-intent",
        data=json.dumps({}),
        content_type="application/json",
    )

    assert response.status_code == 201, response.content
    payload = response.json()

    assert payload["order_id"] == str(order.id)
    assert payload["provider"] == "fake"
    assert payload["amount_cents"] == 2400
    assert payload["currency"] == "EUR"
    assert payload["status"] == "CREATED"
    assert payload["provider_intent_id"].startswith("pi_fake_")
    assert payload["client_secret"].startswith("secret_")


def test_payment_intent_endpoint_replays_idempotency_key(order, buyer):
    client = Client()
    client.force_login(buyer)
    url = f"/api/v1/orders/{order.id}/payment-intent"

    first = client.post(
        url,
        data=json.dumps({}),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="payment-intent-replay-key",
    )
    replay = client.post(
        url,
        data=json.dumps({}),
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="payment-intent-replay-key",
    )

    assert first.status_code == 201, first.content
    assert replay.status_code == 201, replay.content
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json() == first.json()
    assert PaymentIntent.objects.filter(order=order).count() == 1
