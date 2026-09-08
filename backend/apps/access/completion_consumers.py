from apps.catalog.events import CATALOG_EVENT_COMPLETED
from apps.core.outbox.consumer import BaseConsumer
from apps.core.outbox.models import OutboxEvent

from .services.admission_sessions import close_event_admission_automatically


class EventCompletionAdmissionConsumer(BaseConsumer):
    """Ferme la session d'entrée après la clôture automatique d'un événement."""

    name = "access.event_completion_admission"
    handled_event_types = {CATALOG_EVENT_COMPLETED}

    def handle(self, event: OutboxEvent) -> None:
        close_event_admission_automatically(
            event_id=event.aggregate_id,
        )
