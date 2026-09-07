from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class EventAdmissionSession(UUIDModel, TimeStampedModel):
    """
    Période pendant laquelle les scanners peuvent valider les billets
    d'un événement. Une seule session ouverte est autorisée par événement.
    """

    event = models.ForeignKey(
        "catalog.Event",
        on_delete=models.CASCADE,
        related_name="admission_sessions",
    )
    opened_at = models.DateTimeField()
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="opened_admission_sessions",
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="closed_admission_sessions",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "access_event_admission_session"
        constraints = [
            models.UniqueConstraint(
                fields=["event"],
                condition=models.Q(closed_at__isnull=True),
                name="uq_admission_session_event_open",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(closed_at__isnull=True, closed_by__isnull=True)
                    | models.Q(closed_at__isnull=False, closed_by__isnull=False)
                ),
                name="ck_admission_session_closure_trace",
            ),
        ]
        indexes = [
            models.Index(
                fields=["event", "closed_at"],
                name="ix_access_admit_evt_open",
            ),
        ]


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
