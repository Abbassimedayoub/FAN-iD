from apps.catalog.events import CATALOG_EVENT_COMPLETED
from apps.catalog.models import Event
from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent
from apps.core.outbox.publisher import publish_event

from .events import ACCESS_FINAL_REPORT_READY, AGGREGATE_FINAL_REPORT
from .services.final_reports import build_event_final_report


class EventCompletionFinalReportConsumer(BaseConsumer):
    """Create the final snapshot and schedule the organizer email after commit."""

    name = "access.event_completion_final_report"
    handled_event_types = {CATALOG_EVENT_COMPLETED}

    def handle(self, event: OutboxEvent) -> None:
        # Legacy data may contain completed events without an organizer; those events
        # are not eligible for a commercial final report.
        organizer_id = (
            Event.objects.only("organizer_id")
            .get(
                pk=event.aggregate_id,
            )
            .organizer_id
        )
        if organizer_id is None:
            return

        report = build_event_final_report(
            event_id=event.aggregate_id,
        )
        publish_event(
            event_type=ACCESS_FINAL_REPORT_READY,
            aggregate_type=AGGREGATE_FINAL_REPORT,
            aggregate_id=report.id,
            payload={
                "event_id": str(report.event_id),
            },
        )
