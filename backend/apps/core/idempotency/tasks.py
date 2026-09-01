import logging

from celery import shared_task

from . import service

logger = logging.getLogger("fanid.idempotency")


@shared_task(name="core.idempotency.purge_expired")
def purge_expired_idempotency_records() -> int:
    """Tâche Celery Beat quotidienne (§20 master prompt)."""
    deleted = service.purge_expired()
    logger.info("idempotency_purge_completed", extra={"deleted_count": deleted})
    return deleted
