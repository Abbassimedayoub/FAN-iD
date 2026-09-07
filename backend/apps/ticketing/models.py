from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


TICKET_VALID = "VALID"
TICKET_USED = "USED"
TICKET_VOID = "VOID"

TICKET_STATUSES = (
    TICKET_VALID,
    TICKET_USED,
    TICKET_VOID,
)


class Ticket(UUIDModel, TimeStampedModel):
    """Billet individuel émis uniquement après confirmation du paiement."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    order_line = models.ForeignKey(
        "ordering.OrderLine",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    event = models.ForeignKey(
        "catalog.Event",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    ticket_category = models.ForeignKey(
        "catalog.TicketCategory",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    sequence = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=16,
        default=TICKET_VALID,
        choices=[(status, status) for status in TICKET_STATUSES],
    )

    class Meta:
        db_table = "ticketing_ticket"
        constraints = [
            models.UniqueConstraint(
                fields=["order_line", "sequence"],
                name="uq_ticket_line_sequence",
            ),
            models.CheckConstraint(
                condition=models.Q(sequence__gt=0),
                name="ck_ticket_sequence_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=list(TICKET_STATUSES)),
                name="ck_ticket_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "created_at"],
                name="ix_ticket_user_created",
            ),
            models.Index(
                fields=["event", "status"],
                name="ix_ticket_event_status",
            ),
        ]
