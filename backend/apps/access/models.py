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
    scheduled_starts_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de début de la programmation pour laquelle la session a été ouverte.",
    )
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
    closed_automatically = models.BooleanField(default=False)

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
                    models.Q(
                        closed_at__isnull=True,
                        closed_by__isnull=True,
                        closed_automatically=False,
                    )
                    | models.Q(
                        closed_at__isnull=False,
                        closed_by__isnull=False,
                        closed_automatically=False,
                    )
                    | models.Q(
                        closed_at__isnull=False,
                        closed_by__isnull=True,
                        closed_automatically=True,
                    )
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


class ScannerPresence(UUIDModel, TimeStampedModel):
    """Dernier signal reçu d'une application Scanner active."""

    scanner = models.OneToOneField(
        "organizing.Scanner",
        on_delete=models.PROTECT,
        related_name="access_presence",
    )
    last_seen_at = models.DateTimeField()

    class Meta:
        db_table = "access_scanner_presence"


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


class EventFinalReport(UUIDModel, TimeStampedModel):
    """
    Snapshot financier et opérationnel immuable à la clôture d'un événement.

    Les données sources peuvent évoluer techniquement après coup ; le rapport
    final reste la trace de référence remise à l'Organizer.
    """

    event = models.OneToOneField(
        "catalog.Event",
        on_delete=models.PROTECT,
        related_name="final_report",
    )
    generated_at = models.DateTimeField()

    tickets_sold_count = models.PositiveIntegerField(default=0)
    tickets_used_count = models.PositiveIntegerField(default=0)
    tickets_voided_count = models.PositiveIntegerField(default=0)
    tickets_absent_count = models.PositiveIntegerField(default=0)

    gross_revenue_cents = models.PositiveIntegerField(default=0)
    refunds_cents = models.PositiveIntegerField(default=0)
    net_revenue_cents = models.PositiveIntegerField(default=0)

    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0,
    )
    commission_cents = models.PositiveIntegerField(default=0)
    organizer_net_cents = models.PositiveIntegerField(default=0)

    scanner_stats = models.JSONField(default=list)

    class Meta:
        db_table = "access_event_final_report"
        indexes = [
            models.Index(
                fields=["generated_at"],
                name="ix_final_report_generated",
            ),
        ]
