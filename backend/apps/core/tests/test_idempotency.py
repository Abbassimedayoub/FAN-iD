"""
Idempotency concurrency tests: five concurrent requests with one key yield one
real execution; a reused key with a different body returns 422; and orphaned
in-progress records are recovered after the guard interval.

These tests require real PostgreSQL for true multi-connection concurrency.
"""

import threading
from datetime import timedelta

import pytest
from django.db import connections
from django.utils import timezone

from apps.core import exceptions
from apps.core.idempotency import service
from apps.core.idempotency.models import IdempotencyRecord


@pytest.mark.django_db(transaction=True)
def test_five_concurrent_requests_same_key_yield_one_execution(user):
    """
    Five threads call begin() with the same key. Exactly one may receive
    `replayed=False`; the others must replay or observe RequestInProgressError,
    never execute the operation a second time.
    """
    key = "purchase-key-concurrent-1"
    results: list[tuple[str, bool | None]] = []
    lock = threading.Lock()

    def worker():
        connections.close_all()  # each thread gets its own database connection
        try:
            outcome = service.begin(
                key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="h1"
            )
            with lock:
                results.append(("ok", outcome.replayed))
        except exceptions.RequestInProgressError:
            with lock:
                results.append(("in_progress", None))
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    real_executions = [r for r in results if r == ("ok", False)]
    assert len(real_executions) == 1, f"attendu exactement 1 exécution réelle, obtenu: {results}"

    rejected_or_replayed = [r for r in results if r != ("ok", False)]
    assert len(rejected_or_replayed) == 4


@pytest.mark.django_db
def test_same_key_different_body_is_rejected(user):
    key = "purchase-key-2"
    outcome = service.begin(
        key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-a"
    )
    service.complete(outcome.record, response_status=201, response_body={"order_id": "1"})

    with pytest.raises(exceptions.IdempotencyKeyReuseError) as exc_info:
        service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-b")

    assert exc_info.value.code == "IDEMPOTENCY_KEY_REUSE"


@pytest.mark.django_db
def test_same_key_same_body_replays_completed_response(user):
    key = "purchase-key-3"
    outcome = service.begin(
        key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-a"
    )
    service.complete(outcome.record, response_status=201, response_body={"order_id": "42"})

    replayed = service.begin(
        key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-a"
    )

    assert replayed.replayed is True
    assert replayed.record.response_body == {"order_id": "42"}


@pytest.mark.django_db
def test_in_progress_execution_rejects_immediate_retry(user):
    key = "purchase-key-4"
    service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-a")

    with pytest.raises(exceptions.RequestInProgressError):
        service.begin(key=key, user_id=user.pk, endpoint="/api/v1/tickets/purchase", request_hash="hash-a")


@pytest.mark.django_db
def test_orphaned_in_progress_record_is_recovered_after_guard_delay(user, settings):
    """
    A process that dies between IN_PROGRESS and COMPLETED leaves an orphan.
    After the guard interval the record must be recoverable.
    """
    from unittest.mock import patch

    settings.IDEMPOTENCY_ORPHAN_GUARD_SECONDS = 60
    key = "purchase-key-5"

    record = IdempotencyRecord.objects.create(
        key=key,
        user_id=user.pk,
        endpoint="/api/v1/tickets/purchase",
        request_hash="hash-a",
        status=IdempotencyRecord.Status.IN_PROGRESS,
        expires_at=timezone.now() + timedelta(hours=24),
    )

    # Simulate a record locked more than 60 seconds ago.
    IdempotencyRecord.objects.filter(pk=record.pk).update(locked_at=timezone.now() - timedelta(seconds=61))

    # Verify that orphan recovery emits a WARNING log.
    with patch("apps.core.idempotency.service.logger.warning") as warning_mock:
        outcome = service.begin(
            key=key,
            user_id=user.pk,
            endpoint="/api/v1/tickets/purchase",
            request_hash="hash-a",
        )

    assert outcome.replayed is False
    assert outcome.record.status == IdempotencyRecord.Status.IN_PROGRESS

    warning_mock.assert_called_once()
    assert warning_mock.call_args.args[0] == "idempotency_orphan_recovered"


@pytest.mark.django_db
def test_key_is_scoped_per_user_not_global(user, other_user):
    """Different users may reuse the same client key without interfering."""
    key = "shared-client-generated-key"
    outcome_a = service.begin(key=key, user_id=user.pk, endpoint="/api/v1/x", request_hash="h")
    outcome_b = service.begin(key=key, user_id=other_user.pk, endpoint="/api/v1/x", request_hash="h")

    assert outcome_a.replayed is False
    assert outcome_b.replayed is False
    assert outcome_a.record.pk != outcome_b.record.pk
