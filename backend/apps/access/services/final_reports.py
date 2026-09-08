from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from django.db import transaction
from django.db.models import Count, F, Max, Sum
from django.utils import timezone

from apps.catalog.models import Event
from apps.ordering.models import ORDER_PAID, OrderLine
from apps.organizing.models import Scanner
from apps.payments.models import PAYMENT_REFUND_SUCCEEDED, PaymentRefund
from apps.ticketing.models import TICKET_USED, TICKET_VOID, Ticket

from ..models import EventFinalReport, TicketAdmission


def _commission_cents(*, amount_cents: int, rate: Decimal) -> int:
    return int(
        (
            Decimal(amount_cents) * rate
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


@transaction.atomic
def build_event_final_report(*, event_id: UUID) -> EventFinalReport:
    """
    Crée une seule fois le rapport final d'un événement terminé.

    Le verrou Event et la contrainte OneToOne garantissent l'idempotence,
    même si le worker ou l'outbox rejoue l'événement de clôture.
    """
    # Organizer est une relation nullable : ne pas le joindre pendant
    # SELECT FOR UPDATE, sinon PostgreSQL refuse de verrouiller ce côté externe.
    event = Event.objects.select_for_update().get(pk=event_id)

    existing = EventFinalReport.objects.filter(event=event).first()
    if existing is not None:
        return existing

    if event.status != Event.COMPLETED:
        raise ValueError("EVENT_NOT_COMPLETED")

    tickets = Ticket.objects.filter(event=event)
    tickets_sold_count = tickets.count()
    tickets_used_count = tickets.filter(status=TICKET_USED).count()
    tickets_voided_count = tickets.filter(status=TICKET_VOID).count()
    tickets_absent_count = max(
        tickets_sold_count - tickets_used_count - tickets_voided_count,
        0,
    )

    gross_revenue_cents = int(
        OrderLine.objects.filter(
            order__status=ORDER_PAID,
            ticket_category__event=event,
        ).aggregate(
            total=Sum(
                F("quantity") * F("unit_price_cents"),
            )
        )["total"]
        or 0
    )

    refunds_cents = int(
        PaymentRefund.objects.filter(
            event=event,
            status=PAYMENT_REFUND_SUCCEEDED,
        ).aggregate(total=Sum("amount_cents"))["total"]
        or 0
    )
    net_revenue_cents = max(
        gross_revenue_cents - refunds_cents,
        0,
    )

    commission_rate = (
        event.organizer.commission_rate
        if event.organizer_id is not None
        else Decimal("0")
    )
    commission_cents = _commission_cents(
        amount_cents=net_revenue_cents,
        rate=commission_rate,
    )
    organizer_net_cents = max(
        net_revenue_cents - commission_cents,
        0,
    )

    scan_rows = list(
        TicketAdmission.objects.filter(
            ticket__event=event,
        )
        .values("scanner_id")
        .annotate(
            scan_count=Count("id"),
            last_scan_at=Max("admitted_at"),
        )
        .order_by("scanner_id")
    )
    scanner_by_id = {
        scanner.id: scanner
        for scanner in Scanner.objects.filter(
            pk__in=[row["scanner_id"] for row in scan_rows],
        ).select_related("user")
    }

    scanner_stats = []
    for row in scan_rows:
        scanner = scanner_by_id.get(row["scanner_id"])
        if scanner is None:
            continue

        name = " ".join(
            value
            for value in [
                scanner.user.first_name,
                scanner.user.last_name,
            ]
            if value
        ) or scanner.user.email

        scanner_stats.append(
            {
                "scanner_id": str(scanner.id),
                "name": name,
                "email": scanner.user.email,
                "scan_count": int(row["scan_count"]),
                "last_scan_at": (
                    row["last_scan_at"].isoformat()
                    if row["last_scan_at"] is not None
                    else None
                ),
            }
        )

    return EventFinalReport.objects.create(
        event=event,
        generated_at=timezone.now(),
        tickets_sold_count=tickets_sold_count,
        tickets_used_count=tickets_used_count,
        tickets_voided_count=tickets_voided_count,
        tickets_absent_count=tickets_absent_count,
        gross_revenue_cents=gross_revenue_cents,
        refunds_cents=refunds_cents,
        net_revenue_cents=net_revenue_cents,
        commission_rate=commission_rate,
        commission_cents=commission_cents,
        organizer_net_cents=organizer_net_cents,
        scanner_stats=scanner_stats,
    )
