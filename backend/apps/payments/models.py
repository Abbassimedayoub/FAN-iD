from __future__ import annotations

from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel

PAYMENT_INTENT_CREATED = "CREATED"
PAYMENT_INTENT_SUCCEEDED = "SUCCEEDED"
PAYMENT_INTENT_FAILED = "FAILED"

PAYMENT_INTENT_STATUSES = (
    PAYMENT_INTENT_CREATED,
    PAYMENT_INTENT_SUCCEEDED,
    PAYMENT_INTENT_FAILED,
)


class PaymentIntent(UUIDModel, TimeStampedModel):
    """
    Tentative de paiement associée à une commande.

    Les données du fournisseur sont figées afin de pouvoir traiter un webhook
    de manière idempotente dans l'étape suivante.
    """

    order = models.ForeignKey(
        "ordering.Order",
        on_delete=models.PROTECT,
        related_name="payment_intents",
    )

    provider = models.CharField(max_length=40)

    provider_intent_id = models.CharField(max_length=200, unique=True)

    amount_cents = models.PositiveIntegerField()

    currency = models.CharField(max_length=3, default="EUR")

    status = models.CharField(
        max_length=20,
        default=PAYMENT_INTENT_CREATED,
        choices=[(value, value) for value in PAYMENT_INTENT_STATUSES],
    )

    client_secret = models.CharField(max_length=255)

    class Meta:
        db_table = "payments_payment_intent"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_cents__gt=0),
                name="ck_payment_intent_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=list(PAYMENT_INTENT_STATUSES)),
                name="ck_payment_intent_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["order", "created_at"],
                name="ix_pay_int_order_created",
            ),
            models.Index(
                fields=["status"],
                name="ix_pay_int_status",
            ),
        ]


PAYMENT_REFUND_PENDING = "PENDING"
PAYMENT_REFUND_SUCCEEDED = "SUCCEEDED"
PAYMENT_REFUND_FAILED = "FAILED"

PAYMENT_REFUND_STATUSES = (
    PAYMENT_REFUND_PENDING,
    PAYMENT_REFUND_SUCCEEDED,
    PAYMENT_REFUND_FAILED,
)


class PaymentRefund(UUIDModel, TimeStampedModel):
    """
    Remboursement d'une part de paiement due à l'annulation d'un événement.

    Une même intention Stripe ne peut être remboursée qu'une seule fois pour
    un événement donné. Cette contrainte rend les retries idempotents.
    """

    payment_intent = models.ForeignKey(
        PaymentIntent,
        on_delete=models.PROTECT,
        related_name="refunds",
    )
    event = models.ForeignKey(
        "catalog.Event",
        on_delete=models.PROTECT,
        related_name="payment_refunds",
    )
    amount_cents = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        default=PAYMENT_REFUND_PENDING,
        choices=[(value, value) for value in PAYMENT_REFUND_STATUSES],
    )
    provider_refund_id = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        unique=True,
    )
    failure_reason = models.TextField(
        blank=True,
        default="",
    )

    class Meta:
        db_table = "payments_payment_refund"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_cents__gt=0),
                name="ck_payment_refund_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=list(PAYMENT_REFUND_STATUSES)),
                name="ck_payment_refund_status_valid",
            ),
            models.UniqueConstraint(
                fields=["payment_intent", "event"],
                name="uq_payment_refund_intent_event",
            ),
        ]
        indexes = [
            models.Index(
                fields=["event", "status"],
                name="ix_pay_ref_event_status",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="ix_pay_ref_status_created",
            ),
        ]
