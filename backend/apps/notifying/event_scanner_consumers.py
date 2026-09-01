from __future__ import annotations

from apps.catalog.events import (
    CATALOG_EVENT_CANCELLED,
    CATALOG_EVENT_POSTPONED,
    CATALOG_EVENT_SCANNER_ASSIGNED,
    CATALOG_EVENT_SCANNER_UNASSIGNED,
    CATALOG_EVENT_SUSPENDED,
)
from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent

from .event_scanner_tasks import send_event_scanner_assignment_emails, send_event_scanner_lifecycle_emails


class EventScannerNotificationConsumer(
    BaseConsumer,
):
    """
    Transforme les événements Catalog en tâches e-mail.

    Aucun SMTP n'est exécuté sous le verrou Outbox.
    """

    name = "notifying.event_scanner_notifications"

    handled_event_types = {
        CATALOG_EVENT_SCANNER_ASSIGNED,
        CATALOG_EVENT_SCANNER_UNASSIGNED,
        CATALOG_EVENT_POSTPONED,
        CATALOG_EVENT_SUSPENDED,
        CATALOG_EVENT_CANCELLED,
    }

    def handle(
        self,
        event: OutboxEvent,
    ) -> None:
        event_id = str(event.aggregate_id)

        if event.event_type in {
            CATALOG_EVENT_SCANNER_ASSIGNED,
            CATALOG_EVENT_SCANNER_UNASSIGNED,
        }:
            scanner_id = event.payload.get("scanner_id")

            if not scanner_id:
                return

            change = "ASSIGNED" if event.event_type == CATALOG_EVENT_SCANNER_ASSIGNED else "UNASSIGNED"

            self.defer(
                lambda: (
                    send_event_scanner_assignment_emails.delay(
                        event_id=event_id,
                        scanner_id=str(scanner_id),
                        change=change,
                    )
                )
            )

            return

        self.defer(
            lambda: (
                send_event_scanner_lifecycle_emails.delay(
                    event_id=event_id,
                    change=event.event_type,
                )
            )
        )
