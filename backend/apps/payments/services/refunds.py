from __future__ import annotations

from uuid import UUID

from django.db import transaction

from apps.ordering.api import get_order_event_amount_cents, list_paid_order_ids_for_event
from apps.payments.models import (
    PAYMENT_INTENT_SUCCEEDED,
    PAYMENT_REFUND_PENDING,
    PaymentIntent,
    PaymentRefund,
)


@transaction.atomic
def request_event_refunds(*, event_id: UUID) -> list[PaymentRefund]:
    """
    Prepare refunds for paid orders containing tickets for the cancelled event.

    Amounts come from snapshotted order lines. A unique payment-plus-event
    constraint makes Outbox retries safe, and no provider network call happens
    in this preparation step.
    """
    paid_order_ids = list_paid_order_ids_for_event(
        event_id=event_id,
    )
    matching_payment_intent_ids = PaymentIntent.objects.filter(
        status=PAYMENT_INTENT_SUCCEEDED,
        order_id__in=paid_order_ids,
    ).values("pk")

    payment_intents = (
        PaymentIntent.objects.select_for_update()
        .filter(pk__in=matching_payment_intent_ids)
        .order_by("created_at", "pk")
    )

    refunds: list[PaymentRefund] = []

    for payment_intent in payment_intents:
        amount_cents = get_order_event_amount_cents(
            order_id=payment_intent.order_id,
            event_id=event_id,
        )
        if amount_cents <= 0:
            continue

        refund, _ = PaymentRefund.objects.get_or_create(
            payment_intent=payment_intent,
            event_id=event_id,
            defaults={
                "amount_cents": amount_cents,
                "status": PAYMENT_REFUND_PENDING,
            },
        )
        refunds.append(refund)

    return refunds


class PaymentRefundGatewayError(RuntimeError):
    """The payment provider rejected or did not complete the refund."""


def _refund_idempotency_key(refund: PaymentRefund) -> str:
    return f"fanid-refund:{refund.event_id}:{refund.payment_intent_id}"


def _publish_refund_succeeded(refund: PaymentRefund) -> None:
    from apps.core.outbox.publisher import publish_event

    from ..events import AGGREGATE_PAYMENT_REFUND, PAYMENT_REFUND_SUCCEEDED

    publish_event(
        event_type=PAYMENT_REFUND_SUCCEEDED,
        aggregate_type=AGGREGATE_PAYMENT_REFUND,
        aggregate_id=refund.id,
        payload={
            "event_id": str(refund.event_id),
            "order_id": str(refund.payment_intent.order_id),
            "amount_cents": refund.amount_cents,
        },
    )


def execute_payment_refund(*, refund_id: UUID, gateway) -> PaymentRefund:
    """
    Execute the provider refund and cancel tickets only after confirmed success.

    The external call stays outside the SQL transaction; the provider
    idempotency key protects retries and concurrent workers.
    """
    refund = PaymentRefund.objects.select_related(
        "payment_intent",
    ).get(pk=refund_id)

    if refund.status == "SUCCEEDED":
        return refund

    gateway_provider = getattr(gateway, "provider_name", None)
    if refund.payment_intent.provider != gateway_provider:
        raise PaymentRefundGatewayError("La passerelle de remboursement ne correspond pas au paiement.")

    try:
        provider_refund = gateway.create_refund(
            payment_intent_id=refund.payment_intent.provider_intent_id,
            amount_cents=refund.amount_cents,
            idempotency_key=_refund_idempotency_key(refund),
        )
    except Exception as exc:
        with transaction.atomic():
            locked_refund = PaymentRefund.objects.select_for_update().get(
                pk=refund_id,
            )
            if locked_refund.status != "SUCCEEDED":
                locked_refund.status = "FAILED"
                locked_refund.failure_reason = str(exc)[:2000]
                locked_refund.save(
                    update_fields=["status", "failure_reason"],
                )
        raise PaymentRefundGatewayError() from exc

    provider_status = str(provider_refund.get("status", "")).lower()

    with transaction.atomic():
        locked_refund = (
            PaymentRefund.objects.select_for_update()
            .select_related(
                "payment_intent",
            )
            .get(pk=refund_id)
        )

        if locked_refund.status == "SUCCEEDED":
            return locked_refund

        locked_refund.provider_refund_id = str(provider_refund["id"])

        if provider_status == "succeeded":
            from apps.ticketing.api import void_valid_tickets_for_order_event

            void_valid_tickets_for_order_event(
                event_id=locked_refund.event_id,
                order_id=locked_refund.payment_intent.order_id,
            )

            locked_refund.status = "SUCCEEDED"
            locked_refund.failure_reason = ""
            locked_refund.save(
                update_fields=[
                    "provider_refund_id",
                    "status",
                    "failure_reason",
                ],
            )
            _publish_refund_succeeded(locked_refund)
            return locked_refund

        if provider_status in {"pending", "processing"}:
            locked_refund.status = "PENDING"
            locked_refund.failure_reason = ""
            locked_refund.save(
                update_fields=[
                    "provider_refund_id",
                    "status",
                    "failure_reason",
                ],
            )
            return locked_refund

        locked_refund.status = "FAILED"
        locked_refund.failure_reason = (
            f"Statut remboursement fournisseur inattendu : {provider_status or 'inconnu'}"
        )
        locked_refund.save(
            update_fields=[
                "provider_refund_id",
                "status",
                "failure_reason",
            ],
        )

    raise PaymentRefundGatewayError()


@transaction.atomic
def mark_payment_refund_succeeded(*, provider_refund_id: str) -> PaymentRefund:
    """Finalize a refund later confirmed by Stripe."""

    locked_refund = (
        PaymentRefund.objects.select_for_update()
        .select_related(
            "payment_intent",
        )
        .get(provider_refund_id=provider_refund_id)
    )

    if locked_refund.status == "SUCCEEDED":
        return locked_refund

    from apps.ticketing.api import void_valid_tickets_for_order_event

    void_valid_tickets_for_order_event(
        event_id=locked_refund.event_id,
        order_id=locked_refund.payment_intent.order_id,
    )

    locked_refund.status = "SUCCEEDED"
    locked_refund.failure_reason = ""
    locked_refund.save(update_fields=["status", "failure_reason"])

    _publish_refund_succeeded(locked_refund)
    return locked_refund


@transaction.atomic
def mark_payment_refund_failed(
    *,
    provider_refund_id: str,
    failure_reason: str,
) -> PaymentRefund:
    """Persist the terminal failure reported by the Stripe webhook."""

    locked_refund = PaymentRefund.objects.select_for_update().get(
        provider_refund_id=provider_refund_id,
    )

    if locked_refund.status == "SUCCEEDED":
        return locked_refund

    locked_refund.status = "FAILED"
    locked_refund.failure_reason = failure_reason[:2000]
    locked_refund.save(update_fields=["status", "failure_reason"])
    return locked_refund
