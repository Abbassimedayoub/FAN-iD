"""Public read interface for the access context."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .models import EventFinalReport


@dataclass(frozen=True, slots=True)
class FinalReportEventSummary:
    id: uuid.UUID
    name: str
    ends_at: datetime


@dataclass(frozen=True, slots=True)
class FinalReportOrganizerSummary:
    recipient_email: str
    first_name: str


@dataclass(frozen=True, slots=True)
class EventFinalReportNotificationSummary:
    """Immutable final-report data exposed to notification adapters."""

    event: FinalReportEventSummary
    organizer: FinalReportOrganizerSummary
    generated_at: datetime
    tickets_sold_count: int
    tickets_used_count: int
    tickets_voided_count: int
    tickets_absent_count: int
    gross_revenue_cents: int
    refunds_cents: int
    net_revenue_cents: int
    commission_cents: int
    organizer_net_cents: int
    scanner_stats: list[dict[str, Any]]


def get_event_final_report_notification_summary(
    *,
    event_id: uuid.UUID | str,
) -> EventFinalReportNotificationSummary | None:
    """Return the immutable data required to deliver a final report."""
    report = (
        EventFinalReport.objects.select_related(
            "event",
            "event__organizer__user",
        )
        .filter(event_id=event_id)
        .first()
    )

    if report is None or report.event.organizer is None:
        return None

    organizer = report.event.organizer

    return EventFinalReportNotificationSummary(
        event=FinalReportEventSummary(
            id=report.event_id,
            name=report.event.name,
            ends_at=report.event.ends_at,
        ),
        organizer=FinalReportOrganizerSummary(
            recipient_email=organizer.contact_email or organizer.user.email,
            first_name=organizer.user.first_name,
        ),
        generated_at=report.generated_at,
        tickets_sold_count=report.tickets_sold_count,
        tickets_used_count=report.tickets_used_count,
        tickets_voided_count=report.tickets_voided_count,
        tickets_absent_count=report.tickets_absent_count,
        gross_revenue_cents=report.gross_revenue_cents,
        refunds_cents=report.refunds_cents,
        net_revenue_cents=report.net_revenue_cents,
        commission_cents=report.commission_cents,
        organizer_net_cents=report.organizer_net_cents,
        scanner_stats=list(report.scanner_stats),
    )
