"""
BaseConsumer — consommateurs idempotents (§22/§23 master prompt, ADR-S-03).

La livraison Outbox est *at-least-once* : chaque consommateur DOIT être
idempotent. La table `consumed_event` (PK composite `(consumer_name,
event_id)`) est le mécanisme de déduplication : l'insertion est tentée en
DÉBUT de traitement, une IntegrityError signifie "déjà traité".
"""
import logging
from abc import ABC, abstractmethod

from django.db import IntegrityError, transaction

from .models import ConsumedEvent, OutboxEvent

logger = logging.getLogger("fanid.outbox")


class BaseConsumer(ABC):
    name: str  # nom stable, unique par consommateur — clé de `consumed_event`
    handled_event_types: set[str] = set()

    def handles(self, event_type: str) -> bool:
        return event_type in self.handled_event_types

    def consume(self, event: OutboxEvent) -> None:
        with transaction.atomic():
            try:
                ConsumedEvent.objects.create(consumer_name=self.name, event_id=event.id)
            except IntegrityError:
                logger.info(
                    "outbox_event_already_consumed",
                    extra={"consumer": self.name, "event_id": str(event.id)},
                )
                return
            self.handle(event)

    @abstractmethod
    def handle(self, event: OutboxEvent) -> None:
        """Traitement métier de l'événement — implémenté par chaque bounded context."""
        raise NotImplementedError
