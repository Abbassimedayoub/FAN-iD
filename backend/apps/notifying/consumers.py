from __future__ import annotations

from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent
from apps.organizing.constants import ORGANIZER_APPROVED, ORGANIZER_REJECTED, ORGANIZER_SUSPENDED
from apps.organizing.events import (
    ORGANIZER_APPROVED_EVENT,
    ORGANIZER_REJECTED_EVENT,
    ORGANIZER_SUSPENDED_EVENT,
)

from .tasks import send_organizer_decision_email


class OrganizerDecisionEmailConsumer(BaseConsumer):
    """
    Transforme une décision organisateur en tâche e-mail.

    Aucun appel SMTP n'est effectué dans la transaction Outbox.
    """

    name = "notifying.organizer_decision_email"

    handled_event_types = {
        ORGANIZER_APPROVED_EVENT,
        ORGANIZER_REJECTED_EVENT,
        ORGANIZER_SUSPENDED_EVENT,
    }

    def handle(
        self,
        event: OutboxEvent,
    ) -> None:
        decision = event.payload.get("status")

        if decision not in {
            ORGANIZER_APPROVED,
            ORGANIZER_REJECTED,
            ORGANIZER_SUSPENDED,
        }:
            return

        organizer_id = str(event.aggregate_id)

        self.defer(
            lambda: send_organizer_decision_email.delay(
                organizer_id=organizer_id,
                decision=decision,
            )
        )
