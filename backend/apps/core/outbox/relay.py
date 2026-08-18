"""
Relais Outbox — consomme `outbox_event` et publie vers les consommateurs.

Point technique décisif (§21 master prompt / §3.1 Source B) :
`SELECT ... FOR UPDATE SKIP LOCKED` permet à plusieurs relais concurrents de
consommer la file SANS se bloquer et sans traiter deux fois le même
événement. Sans `SKIP LOCKED`, un second worker attendrait le premier et le
débit s'effondrerait.

Corollaire de sécurité (§24 master prompt, audit P1.C.1) : `relay_batch()`
tient ces verrous pour la durée de TOUT le lot. Les consumers appelés par
`_dispatch_to_consumers()` ne doivent donc contenir AUCUN appel réseau
direct — voir la règle absolue et le mécanisme `BaseConsumer.defer()` dans
`consumer.py`.

Backoff exponentiel (2s, 8s, 32s, 2min, 8min) puis `DEAD` après 5 tentatives
— jamais de rejeu infini (§21 master prompt).
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

# Registre des consommateurs — chaque bounded context enregistre les siens
# via `register_consumer()` au chargement de son app (apps.py `ready()`).
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
    Traite un lot d'événements PENDING/FAILED disponibles (`available_at <= now`).

    Toute la fonction s'exécute dans UNE transaction : le SELECT FOR UPDATE
    SKIP LOCKED verrouille les lignes choisies pour la durée du traitement, ce
    qui est exactement ce qui empêche un second relais concurrent de
    sélectionner les mêmes lignes (elles sont "sautées", pas attendues).
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
        except Exception as exc:  # pragma: no cover - chemin d'erreur générique
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
