"""
Transactional event publication.

Absolute rule: `publish_event()` MUST be called inside the same transaction
as the business write that triggered it. An assertion enforces this contract;
calling the function outside a transaction is a bug, not a condition to ignore.
"""

import logging
from typing import Any

from django.db import connection
from django.utils import timezone

from apps.core.observability.context import get_correlation_id

from .models import OutboxEvent

logger = logging.getLogger("fanid.outbox")


def publish_event(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: Any,
    payload: dict,
    actor_id: Any = None,
    causation_id: Any = None,
    event_version: int = 1,
) -> OutboxEvent:
    """
    Insert an event into `outbox_event` within the current transaction.

    Stable event contract:
    { event_id, event_type, event_version, aggregate_type, aggregate_id,
      occurred_at, correlation_id, causation_id, actor_id, payload }
    """
    assert connection.in_atomic_block, (
        "publish_event() doit être appelé à l'intérieur d'une transaction "
        "(@transaction.atomic) — un événement publié hors transaction pourrait "
        "être écrit alors que la donnée métier associée est annulée (rollback), "
        "violant l'invariant I-5."
    )

    event = OutboxEvent.objects.create(
        event_type=event_type,
        event_version=event_version,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        correlation_id=get_correlation_id(),
        causation_id=causation_id,
        actor_id=actor_id,
        occurred_at=timezone.now(),
        available_at=timezone.now(),
    )
    logger.info(
        "outbox_event_created",
        extra={"event_type": event_type, "aggregate_id": str(aggregate_id), "event_id": str(event.id)},
    )
    return event
