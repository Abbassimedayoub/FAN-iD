"""
Publication transactionnelle d'événements (ADR-S-03).

Règle absolue (§23 master prompt) : `publish_event()` DOIT être appelé à
l'intérieur de la même transaction que l'écriture métier qui le déclenche.
On le fait respecter par une assertion — appeler cette fonction hors
transaction est un bug, pas un cas à tolérer silencieusement.
"""
import logging

from django.db import connection
from django.utils import timezone

from apps.core.observability.context import get_correlation_id

from .models import OutboxEvent

logger = logging.getLogger("fanid.outbox")


def publish_event(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id,
    payload: dict,
    actor_id=None,
    causation_id=None,
    event_version: int = 1,
) -> OutboxEvent:
    """
    Insère un événement dans `outbox_event`, dans la transaction courante.

    Contrat d'événement stable (ADR-S-03) :
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
