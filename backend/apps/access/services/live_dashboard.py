from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Max, Sum
from django.utils import timezone

from apps.catalog.models import EventScannerAssignment, TicketCategory
from apps.organizing.constants import SCANNER_ACTIVE
from apps.organizing.models import Scanner
from apps.ticketing.models import TICKET_VOID, Ticket

from .admission_sessions import current_event_admission_session

from ..models import (
    ScannerPresence,
    TicketAdmission,
)


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator * 100) / denominator, 1)


def event_live_dashboard(*, event) -> dict:
    event_id = event.id

    ticketing = TicketCategory.objects.filter(event_id=event_id).aggregate(
        quota_total=Sum("quota"),
    )
    quota_total = int(ticketing["quota_total"] or 0)

    tickets_sold = Ticket.objects.filter(event_id=event_id).exclude(
        status=TICKET_VOID,
    ).count()
    tickets_remaining = max(quota_total - tickets_sold, 0)

    admissions_count = TicketAdmission.objects.filter(
        ticket__event_id=event_id,
    ).count()

    active_session = current_event_admission_session(event=event)

    scanner_ids = list(
        EventScannerAssignment.objects.filter(
            event_id=event_id,
            unassigned_at__isnull=True,
        ).values_list("scanner_id", flat=True)
    )
    scanners = list(
        Scanner.objects.filter(
            pk__in=scanner_ids,
            status=SCANNER_ACTIVE,
        )
        .select_related("user")
        .order_by("user__last_name", "user__first_name", "pk")
    )

    activity_rows = TicketAdmission.objects.filter(
        ticket__event_id=event_id,
        scanner_id__in=[scanner.id for scanner in scanners],
    ).values("scanner_id").annotate(
        scan_count=Count("id"),
        last_activity=Max("admitted_at"),
    )
    activity_by_scanner = {
        row["scanner_id"]: row
        for row in activity_rows
    }

    presence_by_scanner = dict(
        ScannerPresence.objects.filter(
            scanner_id__in=[scanner.id for scanner in scanners],
        ).values_list("scanner_id", "last_seen_at")
    )
    presence_deadline = timezone.now() - timedelta(seconds=90)

    scanner_items = []
    for scanner in scanners:
        activity = activity_by_scanner.get(scanner.id)
        last_activity = activity["last_activity"] if activity else None
        last_seen_at = presence_by_scanner.get(scanner.id)
        is_present = bool(
            last_seen_at and last_seen_at >= presence_deadline
        )

        scanner_items.append(
            {
                "scanner_id": str(scanner.id),
                "name": " ".join(
                    value
                    for value in [
                        scanner.user.first_name,
                        scanner.user.last_name,
                    ]
                    if value
                )
                or scanner.user.email,
                "email": scanner.user.email,
                "scan_count": int(activity["scan_count"]) if activity else 0,
                "last_activity": last_activity,
                "last_seen_at": last_seen_at,
                "is_present": is_present,
            }
        )

    present_count = sum(
        1 for scanner in scanner_items if scanner["is_present"]
    )
    capacity_total = event.capacity_total

    return {
        "event_id": str(event_id),
        "event_name": event.name,
        "generated_at": timezone.now(),
        "admission": {
            "is_open": active_session is not None,
            "opened_at": active_session.opened_at if active_session else None,
        },
        "ticketing": {
            "sold_count": tickets_sold,
            "remaining_count": tickets_remaining,
            "quota_total": quota_total,
        },
        "capacity": {
            "total": capacity_total,
            "entries_count": admissions_count,
            "entry_rate_percent": _percent(admissions_count, tickets_sold),
            "capacity_rate_percent": _percent(
                admissions_count,
                int(capacity_total or 0),
            ),
        },
        "scanners": {
            "assigned_count": len(scanner_items),
            "present_count": present_count,
            "absent_count": len(scanner_items) - present_count,
            "items": scanner_items,
        },
    }
