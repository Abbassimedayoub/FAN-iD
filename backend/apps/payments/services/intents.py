from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import ConflictError, InvalidStateTransitionError, NotFoundBusinessError
from apps.core.interfaces import PaymentGateway
from apps.ordering.api import ReservationExpiredError, confirm_order_payment, lock_order_for_payment_intent
from apps.payments.models import PAYMENT_INTENT_CREATED, PAYMENT_INTENT_SUCCEEDED, PaymentIntent


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

    order = lock_order_for_payment_intent(
        order_id=order_id,
        user_id=user.id,
    )
    if order is None:
        raise NotFoundBusinessError(
            code="ORDER_NOT_FOUND",
        )

    if order.is_paid:
        raise OrderNotPayableError(
            details={
                "order_id": str(order.id),
                "status": order.status,
            },
        )

    if not order.is_pending:
        raise InvalidStateTransitionError(
            details={
                "order_id": str(order.id),
                "status": order.status,
            },
        )

    if order.hold is None:
        raise OrderNotPayableError(
            details={
                "order_id": str(order.id),
                "reason": "stock_hold_missing",
            },
        )

    if order.hold.consumed:
        raise OrderNotPayableError(
            details={
                "order_id": str(order.id),
                "reason": "stock_hold_consumed",
            },
        )

    if order.hold.expires_at <= moment:
        raise ReservationExpiredError(
            details={"order_id": str(order.id)},
        )

    existing = (
        PaymentIntent.objects.filter(
            order_id=order.id,
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
        order_id=order.id,
        provider=getattr(gateway, "provider_name", "unknown"),
        provider_intent_id=provider_intent["id"],
        amount_cents=provider_intent["amount_cents"],
        currency=provider_intent["currency"],
        client_secret=provider_intent["client_secret"],
    )


@transaction.atomic
def mark_payment_intent_succeeded(
    *,
    provider_intent_id: str,
    now=None,
) -> PaymentIntent:
    """
    Finalise l'intent après validation par le fournisseur de paiement.

    Les retries du fournisseur sont sûrs : un intent déjà réussi est renvoyé
    sans incrémenter le stock une seconde fois.
    """
    try:
        intent = PaymentIntent.objects.select_for_update().get(
            provider_intent_id=provider_intent_id,
        )
    except PaymentIntent.DoesNotExist as exc:
        raise NotFoundBusinessError(code="PAYMENT_INTENT_NOT_FOUND") from exc

    if intent.status == PAYMENT_INTENT_SUCCEEDED:
        return intent

    if intent.status != PAYMENT_INTENT_CREATED:
        raise InvalidStateTransitionError(
            details={
                "payment_intent_id": str(intent.id),
                "status": intent.status,
                "target_status": PAYMENT_INTENT_SUCCEEDED,
            },
        )

    confirm_order_payment(order_id=intent.order_id, now=now)

    intent.status = PAYMENT_INTENT_SUCCEEDED
    intent.save(update_fields=["status"])

    return intent
