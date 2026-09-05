from __future__ import annotations

import datetime
import json

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from apps.core.adapters.payments import (
    FakeGateway,
    StripeGateway,
    StripeWebhookSignatureError,
)
from apps.catalog.models import Category, Event, TicketCategory
from apps.ordering.models import Order, StockHold
from apps.ordering.services.reservations import ReservationLine, reserve_stock
from apps.ordering.services.confirmation import ReservationExpiredError
from apps.payments.models import PaymentIntent
from apps.payments.services import (
    create_payment_intent,
    mark_payment_intent_succeeded,
)


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


@pytest.fixture
def reserved_order(buyer):
    category = Category.objects.create(name="Payment reservation category")
    starts_at = timezone.now() + datetime.timedelta(days=7)
    event = Event.objects.create(
        category=category,
        name="Payment reservation event",
        starts_at=starts_at,
        ends_at=starts_at + datetime.timedelta(hours=2),
        capacity_total=10,
        published_at=timezone.now(),
        status="PUBLISHED",
    )
    ticket_category = TicketCategory.objects.create(
        event=event,
        name="Standard",
        quota=10,
        unit_price_cents=1200,
    )
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(ticket_category.id, 2)],
    )
    return order, ticket_category


def test_successful_payment_confirms_order_and_consumes_hold(
    reserved_order,
    buyer,
):
    order, ticket_category = reserved_order
    gateway = FakeGateway()
    intent = create_payment_intent(
        order_id=order.id,
        user=buyer,
        gateway=gateway,
    )

    succeeded = mark_payment_intent_succeeded(
        provider_intent_id=intent.provider_intent_id,
    )

    order.refresh_from_db()
    order.stock_hold.refresh_from_db()
    ticket_category.refresh_from_db()

    assert succeeded.status == "SUCCEEDED"
    assert order.status == "PAID"
    assert order.stock_hold.consumed is True
    assert ticket_category.sold_count == 2


def test_successful_payment_retry_does_not_double_count_stock(
    reserved_order,
    buyer,
):
    order, ticket_category = reserved_order
    gateway = FakeGateway()
    intent = create_payment_intent(
        order_id=order.id,
        user=buyer,
        gateway=gateway,
    )

    first = mark_payment_intent_succeeded(
        provider_intent_id=intent.provider_intent_id,
    )
    second = mark_payment_intent_succeeded(
        provider_intent_id=intent.provider_intent_id,
    )

    ticket_category.refresh_from_db()

    assert first.id == second.id
    assert second.status == "SUCCEEDED"
    assert ticket_category.sold_count == 2


def test_stripe_gateway_maps_payment_intent_without_network():
    class PaymentIntents:
        def create(self, *, params):
            assert params["amount"] == 2400
            assert params["currency"] == "eur"
            assert params["automatic_payment_methods"] == {"enabled": True}
            assert params["metadata"] == {"order_id": "order-123"}

            class Result:
                id = "pi_stripe_test"
                amount = 2400
                currency = "eur"
                metadata = {"order_id": "order-123"}
                client_secret = "pi_stripe_test_secret"

            return Result()

    class Client:
        class v1:
            payment_intents = PaymentIntents()

    gateway = StripeGateway(
        secret_key="sk_test_not_used",
        webhook_secret="whsec_not_used",
        client=Client(),
    )

    intent = gateway.create_intent(
        amount_cents=2400,
        currency="EUR",
        metadata={"order_id": "order-123"},
    )

    assert intent == {
        "id": "pi_stripe_test",
        "amount_cents": 2400,
        "currency": "EUR",
        "metadata": {"order_id": "order-123"},
        "client_secret": "pi_stripe_test_secret",
    }


def test_stripe_webhook_confirms_paid_order(
    reserved_order,
    buyer,
    monkeypatch,
):
    order, ticket_category = reserved_order
    gateway = FakeGateway()
    intent = create_payment_intent(
        order_id=order.id,
        user=buyer,
        gateway=gateway,
    )

    class VerifiedStripeGateway:
        provider_name = "stripe"

        def verify_webhook(self, payload, signature):
            assert signature == "valid-signature"
            return {
                "type": "payment_intent.succeeded",
                "data": {
                    "object": {
                        "id": intent.provider_intent_id,
                    },
                },
            }

    monkeypatch.setattr(
        "apps.payments.views.get_payment_gateway",
        lambda: VerifiedStripeGateway(),
    )

    client = Client()
    response = client.post(
        "/api/v1/payments/stripe/webhook",
        data=b'{"test": true}',
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="valid-signature",
    )

    order.refresh_from_db()
    order.stock_hold.refresh_from_db()
    ticket_category.refresh_from_db()
    intent.refresh_from_db()

    assert response.status_code == 200, response.content
    assert intent.status == "SUCCEEDED"
    assert order.status == "PAID"
    assert order.stock_hold.consumed is True
    assert ticket_category.sold_count == 2


def test_stripe_webhook_rejects_invalid_signature(monkeypatch):
    class InvalidStripeGateway:
        provider_name = "stripe"

        def verify_webhook(self, payload, signature):
            raise StripeWebhookSignatureError("Signature invalide.")

    monkeypatch.setattr(
        "apps.payments.views.get_payment_gateway",
        lambda: InvalidStripeGateway(),
    )

    client = Client()
    response = client.post(
        "/api/v1/payments/stripe/webhook",
        data=b'{}',
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="bad-signature",
    )

    assert response.status_code == 400
    assert response.json() == {"code": "INVALID_STRIPE_SIGNATURE"}


def test_stripe_webhook_is_hidden_when_stripe_is_disabled(monkeypatch):
    monkeypatch.setattr(
        "apps.payments.views.get_payment_gateway",
        lambda: FakeGateway(),
    )

    response = Client().post(
        "/api/v1/payments/stripe/webhook",
        data=b"{}",
        content_type="application/json",
    )

    assert response.status_code == 404
