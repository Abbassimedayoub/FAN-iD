import logging

from celery import shared_task
from django.conf import settings

from . import relay

logger = logging.getLogger("fanid.outbox")


@shared_task(name="core.outbox.relay_batch")
def relay_outbox_batch() -> dict:
    """
    Tâche Celery Beat exécutée toutes les `OUTBOX_RELAY_INTERVAL_SECONDS`
    (§21 master prompt). Plusieurs exécutions concurrentes (deux workers, un
    tick qui déborde sur le suivant) sont sûres par construction :
    `SELECT FOR UPDATE SKIP LOCKED` dans `relay_batch()`.
    """
    result = relay.relay_batch(batch_size=settings.OUTBOX_RELAY_BATCH_SIZE)
    if result.published or result.failed or result.dead:
        logger.info(
            "outbox_relay_tick",
            extra={"published": result.published, "failed": result.failed, "dead": result.dead},
        )
    return {"published": result.published, "failed": result.failed, "dead": result.dead}


@shared_task(name="core.outbox.purge_published")
def purge_published_events() -> int:
    """Purge des événements PUBLISHED de plus de OUTBOX_RETENTION_DAYS (§21 master prompt)."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import OutboxEvent

    cutoff = timezone.now() - timedelta(days=settings.OUTBOX_RETENTION_DAYS)
    deleted, _ = OutboxEvent.objects.filter(
        status=OutboxEvent.Status.PUBLISHED, published_at__lt=cutoff
    ).delete()
    logger.info("outbox_purge_completed", extra={"deleted_count": deleted})
    return deleted
