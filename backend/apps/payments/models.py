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
