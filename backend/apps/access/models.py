from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class TicketAdmission(UUIDModel, TimeStampedModel):
    """Trace immuable de l'admission réussie d'un billet."""

    ticket = models.OneToOneField(
        "ticketing.Ticket",
        on_delete=models.PROTECT,
        related_name="admission",
    )
    scanner = models.ForeignKey(
        "organizing.Scanner",
        on_delete=models.PROTECT,
        related_name="ticket_admissions",
    )
    admitted_at = models.DateTimeField()

    class Meta:
        db_table = "access_ticket_admission"
        indexes = [
            models.Index(
                fields=["scanner", "admitted_at"],
                name="ix_admission_scanner_time",
            ),
        ]
