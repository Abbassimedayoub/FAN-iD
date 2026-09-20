"""
BaseConsumer — idempotent Outbox consumers.

Outbox delivery is at-least-once, so every consumer MUST be idempotent.
The `consumed_event` table, keyed by `(consumer_name, event_id)`, provides
deduplication: insertion is attempted at the START of processing, and an
IntegrityError means the event was already handled.

Absolute rule: `consume()` runs inside the relay transaction, which holds
`SELECT ... FOR UPDATE SKIP LOCKED` locks on the current event batch.
Therefore `handle()` must NEVER perform direct network calls such as email,
push, external HTTP, or payment-provider requests. A slow or blocked call
would hold locks for the entire batch during network latency.

All network side effects MUST use `self.defer(callback)`, which runs only
AFTER the relay transaction commits and the locks are released. `handle()`
should contain only fast local database work and, when necessary, registration
of a deferred callback:

    class NotifyOrderPaidConsumer(BaseConsumer):
        name = "notifying.order_paid_email"
        handled_event_types = {"order.paid"}

        def handle(self, event: OutboxEvent) -> None:
            order_id = event.aggregate_id
            # Do not perform network I/O here. Schedule a Celery task instead.
            self.defer(lambda: send_order_confirmation_email.delay(order_id=str(order_id)))
"""

import logging
from abc import ABC, abstractmethod
from typing import Callable

from django.db import IntegrityError, transaction

from .models import ConsumedEvent, OutboxEvent

logger = logging.getLogger("fanid.outbox")


class BaseConsumer(ABC):
    name: str  # stable name, unique per consumer; key in `consumed_event`
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

    @staticmethod
    def defer(callback: Callable[[], None]) -> None:
        """
        Register `callback` to run AFTER the surrounding transaction commits.
        Django's `transaction.on_commit` defers execution until the outermost
        atomic transaction commits, so the relay batch locks are already
        released when `callback` runs. This is the required mechanism for any
        network side effect triggered by a consumer.
        """
        transaction.on_commit(callback)

    @abstractmethod
    def handle(self, event: OutboxEvent) -> None:
        """
        Process the business event in the bounded context. Database work only;
        all network side effects must go through `self.defer(...)`.
        """
        raise NotImplementedError
