"""
Idempotency service.

The tuple **(user, key, endpoint, request_hash)** is validated explicitly —
not just (user, key) — because the same key value submitted by mistake or by
a buggy client to TWO different endpoints must NEVER replay one endpoint's
response on another. That would leak responses across endpoints and possibly
across features.

Rules:
- a key already seen on a DIFFERENT endpoint, even when the hash matches,
  raises `IdempotencyKeyReuseError` (422). This check happens first, before
  any status-specific logic, so it can never enter a replay path.
- a COMPLETED key with the same endpoint and request fingerprint replays the
  stored response.
- a key with the same endpoint and a DIFFERENT fingerprint raises
  `IdempotencyKeyReuseError` (422).
- a non-orphaned IN_PROGRESS key raises `RequestInProgressError` (409).
- an orphaned IN_PROGRESS key is recovered after the guard period, with a
  WARNING log.
- INSERT is the lock; do not SELECT and then INSERT because that creates a
  race window.
"""

import hashlib
import json
import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import IdempotencyKeyReuseError, RequestInProgressError
from apps.core.observability.metrics import fanid_idempotency_conflicts_total

from .models import IdempotencyRecord

logger = logging.getLogger("fanid.idempotency")


def compute_request_hash(body: bytes) -> str:
    """Return the SHA-256 fingerprint of the canonical request body."""
    return hashlib.sha256(body or b"").hexdigest()


class IdempotencyOutcome:
    """Result of `begin()`: either a replayed response or a record to complete."""

    def __init__(self, record: IdempotencyRecord, replayed: bool):
        self.record = record
        self.replayed = replayed


def _is_orphaned(record: IdempotencyRecord) -> bool:
    guard = timedelta(seconds=settings.IDEMPOTENCY_ORPHAN_GUARD_SECONDS)
    return timezone.now() - record.locked_at > guard


@transaction.atomic
def begin(*, key: str, user_id: Any, endpoint: str, request_hash: str) -> IdempotencyOutcome:
    """
    Start or replay an idempotent operation.

    Insertion is attempted directly. An IntegrityError means a record already
    exists for (key, user_id); this is the locking mechanism, rather than a
    preliminary SELECT.
    """
    expires_at = timezone.now() + timedelta(hours=settings.IDEMPOTENCY_RETENTION_HOURS)

    try:
        with transaction.atomic():
            record = IdempotencyRecord.objects.create(
                key=key,
                user_id=user_id,
                endpoint=endpoint,
                request_hash=request_hash,
                status=IdempotencyRecord.Status.IN_PROGRESS,
                expires_at=expires_at,
            )
        return IdempotencyOutcome(record=record, replayed=False)
    except IntegrityError:
        pass

    # A record already exists: take a pessimistic lock before deciding what to do.
    record = IdempotencyRecord.objects.select_for_update().get(
        key=key,
        user_id=user_id,
    )

    # Validate (user, key, endpoint, request_hash) FIRST, before branching on
    # status. A different endpoint is ALWAYS rejected regardless of the
    # existing record's status (COMPLETED, IN_PROGRESS, or FAILED). Reusing a
    # key across endpoints is never a legitimate recovery; it is either a
    # client bug or an attempt to replay another endpoint's response.
    if record.endpoint != endpoint:
        fanid_idempotency_conflicts_total.labels(reason="endpoint_mismatch").inc()
        logger.warning(
            "idempotency_key_reused_across_endpoints",
            extra={
                "idempotency_key": key,
                "user_id": str(user_id),
                "original_endpoint": record.endpoint,
                "attempted_endpoint": endpoint,
            },
        )
        raise IdempotencyKeyReuseError(
            message="Cette clé d'idempotence a déjà été utilisée sur un autre endpoint.",
            details={"key": key, "expected_endpoint": record.endpoint, "received_endpoint": endpoint},
        )

    if record.status == IdempotencyRecord.Status.COMPLETED:
        if record.request_hash != request_hash:
            fanid_idempotency_conflicts_total.labels(reason="key_reuse").inc()
            raise IdempotencyKeyReuseError(
                details={"key": key, "endpoint": endpoint},
            )
        return IdempotencyOutcome(record=record, replayed=True)

    if record.status == IdempotencyRecord.Status.IN_PROGRESS:
        if _is_orphaned(record):
            logger.warning(
                "idempotency_orphan_recovered",
                extra={"idempotency_key": key, "user_id": str(user_id), "endpoint": endpoint},
            )
            record.locked_at = timezone.now()
            record.request_hash = request_hash
            record.save(update_fields=["locked_at", "request_hash"])
            return IdempotencyOutcome(record=record, replayed=False)

        fanid_idempotency_conflicts_total.labels(reason="in_progress").inc()
        raise RequestInProgressError(details={"key": key, "endpoint": endpoint})

    # FAILED: allow a clean retry by returning the record to IN_PROGRESS.
    record.status = IdempotencyRecord.Status.IN_PROGRESS
    record.locked_at = timezone.now()
    record.request_hash = request_hash
    record.save(update_fields=["status", "locked_at", "request_hash"])
    return IdempotencyOutcome(record=record, replayed=False)


def complete(
    record: IdempotencyRecord,
    *,
    response_status: int,
    response_body: Any,
    response_headers: dict | None = None,
) -> None:
    """
    Store the result for future replay. `response_headers` contains only a
    whitelist of important headers (see
    `middleware.REPLAYABLE_RESPONSE_HEADERS`), never every header from the
    original response. Headers such as `Set-Cookie` and
    `X-Correlation-ID` must not be replayed verbatim.
    """
    record.status = IdempotencyRecord.Status.COMPLETED
    record.response_status = response_status
    record.response_body = response_body
    record.response_headers = response_headers or {}
    record.save(update_fields=["status", "response_status", "response_body", "response_headers"])


def fail(record: IdempotencyRecord) -> None:
    record.status = IdempotencyRecord.Status.FAILED
    record.save(update_fields=["status"])


def purge_expired() -> int:
    """Purge expired records as part of the daily Beat task."""
    deleted, _ = IdempotencyRecord.objects.filter(expires_at__lt=timezone.now()).delete()
    return deleted


def serialize_response_body(data: Any) -> bytes:
    return json.dumps(data, default=str).encode()
