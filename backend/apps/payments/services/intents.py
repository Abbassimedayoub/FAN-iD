from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ConflictError, InvalidStateTransitionError, NotFoundBusinessError
from apps.core.interfaces import PaymentGateway
from apps.ordering.models import ORDER_PAID, ORDER_PENDING, Order, StockHold
from apps.ordering.services.confirmation import ReservationExpiredError
from apps.payments.models import PAYMENT_INTENT_CREATED, PaymentIntent


class OrderNotPayableError(ConflictError):
    default_code = "ORDER_NOT_PAYABLE"
    default_message = "Cette commande ne peut pas être payée."


@transaction.atomic
def create_payment_intent(
    *,
    order_id: UUID,
    user,
    gateway: PaymentGateway,
    currency: str = "EUR",
    now=None,
) -> PaymentIntent:
    """
    Crée ou réutilise l'intent actif de la commande.

    Le gateway est injecté : les tests utilisent FakeGateway, tandis qu'un
    futur adaptateur Stripe pourra être fourni sans modifier cette règle métier.
    """
    moment = now or timezone.now()

    try:
        order = Order.objects.select_for_update().get(
            pk=order_id,
            user=user,
        )
    except Order.DoesNotExist as exc:
        raise NotFoundBusinessError(code="ORDER_NOT_FOUND") from exc

    if order.status == ORDER_PAID:
        raise OrderNotPayableError(
            details={"order_id": str(order.id), "status": order.status},
        )

    if order.status != ORDER_PENDING:
        raise InvalidStateTransitionError(
            details={"order_id": str(order.id), "status": order.status},
        )

    try:
        hold = StockHold.objects.select_for_update().get(order=order)
    except StockHold.DoesNotExist as exc:
        raise OrderNotPayableError(
            details={"order_id": str(order.id), "reason": "stock_hold_missing"},
        ) from exc

    if hold.consumed:
        raise OrderNotPayableError(
            details={"order_id": str(order.id), "reason": "stock_hold_consumed"},
        )

    if hold.expires_at <= moment:
        raise ReservationExpiredError(details={"order_id": str(order.id)})

    existing = (
        PaymentIntent.objects.filter(
            order=order,
            status=PAYMENT_INTENT_CREATED,
        )
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        return existing

    provider_intent = gateway.create_intent(
        amount_cents=order.total_amount_cents,
        currency=currency,
        metadata={
            "order_id": str(order.id),
            "user_id": str(user.id),
        },
    )

    return PaymentIntent.objects.create(
        order=order,
        provider="fake",
        provider_intent_id=provider_intent["id"],
        amount_cents=provider_intent["amount_cents"],
        currency=provider_intent["currency"],
        client_secret=provider_intent["client_secret"],
    )
