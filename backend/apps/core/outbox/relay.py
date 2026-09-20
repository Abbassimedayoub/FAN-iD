"""
Outbox relay — consumes `outbox_event` rows and dispatches them to consumers.

The key concurrency mechanism is `SELECT ... FOR UPDATE SKIP LOCKED`, which
allows multiple relay workers to consume the queue concurrently without
blocking each other or processing the same event twice.

Security corollary: `relay_batch()` holds these locks for the whole batch.
Consumers called by `_dispatch_to_consumers()` must therefore contain NO
direct network calls. See `BaseConsumer.defer()` in `consumer.py`.

Exponential backoff uses 2s, 8s, 32s, 2min, and 8min delays, then marks the
event `DEAD` after 5 attempts. Retries are never infinite.
"""

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.observability.metrics import fanid_outbox_dead, fanid_outbox_pending

from .models import OutboxEvent

logger = logging.getLogger("fanid.outbox")

# Consumer registry: each bounded context registers its consumers through
# `register_consumer()` when its app loads.
_CONSUMER_REGISTRY: list = []


def register_consumer(consumer: Any) -> None:
    _CONSUMER_REGISTRY.append(consumer)


class RelayResult:
    def __init__(self, published: int, failed: int, dead: int):
        self.published = published
        self.failed = failed
        self.dead = dead


@transaction.atomic
def relay_batch(batch_size: int | None = None) -> RelayResult:
    """
    Process a batch of available PENDING/FAILED events
    (`available_at <= now`).

    The whole function runs in one transaction. `SELECT FOR UPDATE SKIP
    LOCKED` locks the selected rows for the duration of processing, preventing
    another concurrent relay from selecting the same rows.
    """
    batch_size = batch_size or settings.OUTBOX_RELAY_BATCH_SIZE
    now = timezone.now()

    events = list(
        OutboxEvent.objects.select_for_update(skip_locked=True)
        .filter(status__in=[OutboxEvent.Status.PENDING, OutboxEvent.Status.FAILED], available_at__lte=now)
        .order_by("sequence")[:batch_size]
    )

    published, failed, dead = 0, 0, 0

    for event in events:
        try:
            _dispatch_to_consumers(event)
        except Exception as exc:  # pragma: no cover - generic error path
            _mark_failed_or_dead(event, exc)
            if event.status == OutboxEvent.Status.DEAD:
                dead += 1
            else:
                failed += 1
            continue

        event.status = OutboxEvent.Status.PUBLISHED
        event.published_at = timezone.now()
        event.save(update_fields=["status", "published_at"])
        published += 1

    _refresh_gauges()
    return RelayResult(published=published, failed=failed, dead=dead)


def _dispatch_to_consumers(event: OutboxEvent) -> None:
    for consumer in _CONSUMER_REGISTRY:
        if consumer.handles(event.event_type):
            consumer.consume(event)


def _mark_failed_or_dead(event: OutboxEvent, exc: Exception) -> None:
    event.attempts += 1
    event.last_error = str(exc)[:2000]

    backoff_schedule = settings.OUTBOX_BACKOFF_SCHEDULE_SECONDS
    if event.attempts >= settings.OUTBOX_MAX_ATTEMPTS:
        event.status = OutboxEvent.Status.DEAD
        logger.error(
            "outbox_event_dead",
            extra={"event_id": str(event.id), "event_type": event.event_type, "attempts": event.attempts},
        )
    else:
        delay = backoff_schedule[min(event.attempts - 1, len(backoff_schedule) - 1)]
        event.status = OutboxEvent.Status.FAILED
        event.available_at = timezone.now() + timedelta(seconds=delay)
        logger.warning(
            "outbox_event_retry_scheduled",
            extra={"event_id": str(event.id), "attempts": event.attempts, "delay_seconds": delay},
        )
    event.save(update_fields=["attempts", "last_error", "status", "available_at"])


def _refresh_gauges() -> None:
    fanid_outbox_pending.set(
        OutboxEvent.objects.filter(status__in=[OutboxEvent.Status.PENDING, OutboxEvent.Status.FAILED]).count()
    )
    fanid_outbox_dead.set(OutboxEvent.objects.filter(status=OutboxEvent.Status.DEAD).count())
